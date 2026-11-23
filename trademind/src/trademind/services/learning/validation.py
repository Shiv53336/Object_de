"""Promotion gate, candidate to paper (PLAN 9.3, DECISIONS D29).

A strategy instance passes only if all five conditions hold. The research confidence level
tightens with every distinct hypothesis ever tested on real research data, across all
strategies (Bonferroni over the research ledger), so trying many variants raises the bar
instead of manufacturing a winner. The bootstrap resamples whole trading days, because trades
on the same day share the market and are not independent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

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


def day_block_lower_bound(r: np.ndarray, days: np.ndarray, confidence: float, resamples: int,
                          seed: int) -> float:
    """Like bootstrap_lower_bound, but resamples trading days (all trades of a day together)."""
    r = np.asarray(r, dtype=float)
    if len(r) == 0:
        return math.nan
    _, groups = np.unique(np.asarray(days), return_inverse=True)
    sums = np.bincount(groups, weights=r)
    counts = np.bincount(groups).astype(float)
    n_days = len(sums)
    rng = np.random.default_rng(seed)
    means = np.empty(resamples)
    batch = max(1, 2_000_000 // max(1, n_days))
    for start in range(0, resamples, batch):
        stop = min(resamples, start + batch)
        idx = rng.integers(0, n_days, size=(stop - start, n_days))
        means[start:stop] = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
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
    research_days: np.ndarray | None = None,
) -> dict:
    k = max(1, research_trials)
    confidence = 1 - 0.05 / k
    n_res, n_hold = len(research_r), len(holdout_r)
    if research_days is None:
        lb = bootstrap_lower_bound(research_r, confidence, v.bootstrap_resamples, v.bootstrap_seed)
    else:
        lb = day_block_lower_bound(research_r, research_days, confidence, v.bootstrap_resamples,
                                   v.bootstrap_seed)
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
    *,
    research_trials: int,
    holdout_evals: int,
) -> dict:
    """`research_trials`: distinct hypotheses in the research ledger. `holdout_evals`: looks at this
    holdout window by this strategy, including this one."""

    def trades_of(run_id: str) -> pd.DataFrame:
        t = journal.read_trades(run_id, instance_id)
        return t[t["strategy_version"] == strategy_version] if not t.empty else t

    research, holdout = trades_of(research_run_id), trades_of(holdout_run_id)
    days = (research["entry_ts"].dt.date.astype(str).to_numpy() if not research.empty
            else np.array([], dtype=str))
    report = evaluate_gate(
        research["r_multiple"].to_numpy(dtype=float) if not research.empty else np.array([]),
        holdout["r_multiple"].to_numpy(dtype=float) if not holdout.empty else np.array([]),
        research_trials,
        holdout_evals,
        v,
        research_days=days,
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


def session_coverage(n_sessions: int | None, start: date, end: date) -> float:
    """Sessions actually simulated as a share of the weekdays in start..end (holidays included,
    so about 0.94 is a complete year on NSE)."""
    weekdays = int(np.busday_count(start, end + timedelta(days=1)))
    return (n_sessions or 0) / weekdays if weekdays else 0.0
