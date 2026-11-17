from __future__ import annotations

import re

import numpy as np
import pytest
from typer.testing import CliRunner

from trademind.cli import app
from trademind.services.learning.validation import bootstrap_lower_bound, evaluate_gate
from trademind.shared.config import AppConfig


def test_bootstrap_lower_bound_properties() -> None:
    rng = np.random.default_rng(1)
    r = rng.normal(0.2, 1.0, 200)
    lb = bootstrap_lower_bound(r, 0.95, 4000, 7)
    assert lb < r.mean()
    assert lb == bootstrap_lower_bound(r, 0.95, 4000, 7)
    big = rng.normal(0.2, 1.0, 5000)
    assert r.mean() - lb > big.mean() - bootstrap_lower_bound(big, 0.95, 2000, 7)
    assert np.isnan(bootstrap_lower_bound(np.array([]), 0.95, 100, 7))


def _gate(cfg: AppConfig, research, holdout, k=1, evals=1):
    v = cfg.settings.validation.model_copy(update={"bootstrap_resamples": 2000})
    rep = evaluate_gate(np.asarray(research, float), np.asarray(holdout, float), k, evals, v)
    return rep, {c.name: c.passed for c in rep["checks"]}


GOOD_RESEARCH = [1.0, -0.5] * 100  # mean 0.25 R, n=200
GOOD_HOLDOUT = [1.0, -0.5] * 20


def test_gate_passes_good_strategy(cfg: AppConfig) -> None:
    rep, _ = _gate(cfg, GOOD_RESEARCH, GOOD_HOLDOUT)
    assert rep["passed"] and rep["confidence"] == pytest.approx(0.95)


def test_bonferroni_uses_trial_count(cfg: AppConfig) -> None:
    rep, _ = _gate(cfg, GOOD_RESEARCH, GOOD_HOLDOUT, k=50)
    assert rep["confidence"] == pytest.approx(1 - 0.05 / 50)


@pytest.mark.parametrize(
    "research,holdout,k,evals,failing",
    [
        ([1.0, -0.5] * 40, GOOD_HOLDOUT, 1, 1, "research_trades"),
        ([0.3, -0.3] * 100, GOOD_HOLDOUT, 1, 1, "research_expectancy_lower_bound_r"),
        ([-1.0] * 20 + [1.0, -0.5] * 100 + [3.0] * 10, GOOD_HOLDOUT, 1, 1, "research_max_drawdown_r"),
        (GOOD_RESEARCH, [1.0, -0.5] * 10, 1, 1, "holdout_trades_and_expectancy_r"),
        (GOOD_RESEARCH, [-0.5, 0.2] * 20, 1, 1, "holdout_trades_and_expectancy_r"),
        (GOOD_RESEARCH, GOOD_HOLDOUT, 1, 3, "holdout_evaluations"),
    ],
)
def test_each_condition_can_fail(cfg: AppConfig, research, holdout, k, evals, failing) -> None:
    rep, passed = _gate(cfg, research, holdout, k, evals)
    assert not rep["passed"] and not passed[failing]
    assert sum(not ok for ok in passed.values()) == 1


def test_cli_validate_flow() -> None:
    runner = CliRunner()
    inst = "orb_momentum@5minute"
    r = runner.invoke(app, ["validate", "--instance", inst, "--start", "2026-05-04", "--end", "2026-05-06"])
    assert r.exit_code == 2 and "research backtest" in r.output
    r = runner.invoke(app, ["backtest", "--start", "2026-04-20", "--end", "2026-04-24", "--instances", inst])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["validate", "--instance", inst, "--start", "2026-04-27", "--end", "2026-05-06"])
    assert r.exit_code == 2 and "on or after" in r.output
    holdout = ["validate", "--instance", inst, "--start", "2026-05-04", "--end", "2026-05-06"]
    for _ in range(2):
        r = runner.invoke(app, holdout)
        assert r.exit_code == 0, r.output
        assert "Promotion gate" in r.output and re.search(r"NOT PASSED|PASSED", r.output)
    r = runner.invoke(app, holdout)
    assert r.exit_code == 2 and "holdout evaluations" in r.output
