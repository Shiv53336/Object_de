"""Promotion gate, candidate to paper (PLAN 9.3).

A strategy instance passes only if all five conditions hold. The research confidence level
tightens with every research trial logged for the strategy (Bonferroni), so trying many
variants raises the bar instead of manufacturing a winner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from trademind.database.journal import Journal
from trademind.services.learning.metrics import max_drawdown
from trademind.shared.config import ValidationConfig


def bootstrap_lower_bound(r: np.ndarray, confidence: float, resamples: int, seed: int) -> float:
    """(1 - confidence) quantile of resampled means: a one-sided lower bound on expectancy."""
    r = np.asarray(r, dtype=float)
    if len(r) == 0:
        return math.nan
    rng = np.random.default_rng(seed)
    means = np.empty(resamples)
    batch = max(1, 2_000_000 // max(1, len(r)))
    for start in range(0, resamples, batch):
        stop = min(resamples, start + batch)
        idx = rng.integers(0, len(r), size=(stop - start, len(r)))
        means[start:stop] = r[idx].mean(axis=1)
    return float(np.quantile(means, 1 - confidence))


@dataclass(frozen=True)
class GateCheck:
    name: str
    value: float | int | None
    threshold: str
    passed: bool


def evaluate_gate(
    research_r: np.ndarray,
    holdout_r: np.ndarray,
    research_trials: int,
    holdout_evals: int,
    v: ValidationConfig,
) -> dict:
    k = max(1, research_trials)
    confidence = 1 - 0.05 / k
    n_res, n_hold = len(research_r), len(holdout_r)
    lb = bootstrap_lower_bound(research_r, confidence, v.bootstrap_resamples, v.bootstrap_seed)
    dd = max_drawdown(np.asarray(research_r, dtype=float))
    hold_exp = float(np.mean(holdout_r)) if n_hold else math.nan
    checks = [
        GateCheck("research_trades", n_res, f">= {v.min_research_trades}", n_res >= v.min_research_trades),
        GateCheck("research_expectancy_lower_bound_r", lb, f"> 0 at {confidence:.4f} (k={k})",
                  bool(not math.isnan(lb) and lb > 0)),
        GateCheck("research_max_drawdown_r", dd, f"<= {v.max_drawdown_r}", dd <= v.max_drawdown_r),
        GateCheck("holdout_trades_and_expectancy_r", hold_exp,
                  f"n >= {v.min_holdout_trades} (n={n_hold}) and > 0",
                  n_hold >= v.min_holdout_trades and not math.isnan(hold_exp) and hold_exp > 0),
        GateCheck("holdout_evaluations", holdout_evals, f"<= {v.max_holdout_evals}",
                  holdout_evals <= v.max_holdout_evals),
    ]
    return {
        "confidence": confidence,
        "research_trials": k,
        "checks": checks,
        "passed": all(c.passed for c in checks),
    }


def promotion_report(
    journal: Journal,
    v: ValidationConfig,
    instance_id: str,
    strategy_version: str,
    research_run_id: str,
    holdout_run_id: str,
) -> dict:
    strategy_id = instance_id.split("@")[0]

    def r_of(run_id: str) -> np.ndarray:
        t = journal.read_trades(run_id, instance_id)
        if not t.empty:
            t = t[t["strategy_version"] == strategy_version]
        return t["r_multiple"].to_numpy(dtype=float) if not t.empty else np.array([])

    report = evaluate_gate(
        r_of(research_run_id),
        r_of(holdout_run_id),
        journal.count_trials(strategy_id, "research"),
        journal.count_holdout_evals(instance_id, strategy_version),
        v,
    )
    return {"instance_id": instance_id, "strategy_version": strategy_version,
            "research_run_id": research_run_id, "holdout_run_id": holdout_run_id, **report}


def format_report(report: dict) -> str:
    lines = [
        f"Promotion gate for {report['instance_id']} v{report['strategy_version']}",
        f"research run {report['research_run_id']}, holdout run {report['holdout_run_id']}",
        "",
        "| check | value | needs | result |",
        "|---|---|---|---|",
    ]
    for c in report["checks"]:
        val = "-" if c.value is None or (isinstance(c.value, float) and math.isnan(c.value)) else (
            f"{c.value:.3f}" if isinstance(c.value, float) else str(c.value))
        lines.append(f"| {c.name} | {val} | {c.threshold} | {'pass' if c.passed else 'FAIL'} |")
    lines += ["", "PASSED: candidate may move to live paper trading." if report["passed"]
              else "NOT PASSED: keep researching; do not trade this version."]
    return "\n".join(lines)
