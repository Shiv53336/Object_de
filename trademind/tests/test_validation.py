from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from trademind.cli import app
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.learning.ledger import ResearchLedger
from trademind.services.learning.validation import bootstrap_lower_bound, evaluate_gate
from trademind.services.market_data.store import ParquetStore
from trademind.services.market_data.synthetic import SyntheticSource
from trademind.shared.config import AppConfig, runtime_paths


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


@pytest.fixture
def real_store(cfg: AppConfig) -> None:
    """Synthetic bars written to the research store, standing in for downloaded market data."""
    s = cfg.settings
    src = SyntheticSource(5, build_instruments(s), s.session, s.market_symbol)
    store = ParquetStore(runtime_paths().bars_dir)
    for sym in build_instruments(s):
        store.write(sym, "1minute", src.get_bars(sym, "1minute", date(2025, 11, 1), date(2026, 5, 8)))


def test_cli_validate_flow(real_store) -> None:
    runner = CliRunner()
    inst = "orb_momentum@5minute"
    hold = ["validate", "--instance", inst, "--source", "parquet",
            "--start", "2026-05-04", "--end", "2026-05-08"]
    r = runner.invoke(app, [*hold[:3], "--source", "synthetic", *hold[5:]])
    assert r.exit_code == 2 and "real market data" in r.output
    r = runner.invoke(app, hold)
    assert r.exit_code == 2 and "no finished research backtest on real data" in r.output

    research = ["backtest", "--start", "2026-04-20", "--end", "2026-04-24", "--instances", inst]
    assert runner.invoke(app, research).exit_code == 0  # synthetic: tells nothing about markets
    assert "no finished research backtest" in runner.invoke(app, hold).output
    r = runner.invoke(app, [*research, "--source", "parquet"])
    assert r.exit_code == 0, r.output
    assert "gross_expectancy_r" in r.output and "cost_per_trade_r" in r.output
    ledger = ResearchLedger(Path(os.environ["TRADEMIND_LEDGER_DIR"]))
    assert ledger.distinct_hypotheses() == 1
    assert runner.invoke(app, [*research, "--source", "parquet"]).exit_code == 0
    assert ledger.distinct_hypotheses() == 1  # a rerun is not a new hypothesis

    r = runner.invoke(app, [*hold[:5], "--start", "2026-04-27", "--end", "2026-05-06"])
    assert r.exit_code == 2 and "fixed window" in r.output
    for k in (1, 2):
        r = runner.invoke(app, hold)
        assert r.exit_code == 0, r.output
        assert "Promotion gate" in r.output and re.search(r"NOT PASSED|PASSED", r.output)
        assert f"Holdout look {k} of 2" in r.output
    r = runner.invoke(app, hold)
    assert r.exit_code == 2 and "used its 2 holdout looks" in r.output
    other_timeframe = [*hold[:2], "orb_momentum@15minute", *hold[3:]]
    r = runner.invoke(app, other_timeframe)
    assert r.exit_code == 2 and "used its 2 holdout looks" in r.output
    assert len(ledger.looks("orb_momentum", (date(2026, 5, 1), date(2026, 10, 31)))) == 2


def test_validate_refuses_a_thin_holdout_without_using_a_look(real_store) -> None:
    runner = CliRunner()
    inst = "orb_momentum@5minute"
    research = ["backtest", "--source", "parquet", "--start", "2026-04-20", "--end", "2026-04-24",
                "--instances", inst]
    assert runner.invoke(app, research).exit_code == 0
    r = runner.invoke(app, ["validate", "--instance", inst, "--source", "parquet", "--start", "2026-05-04",
                            "--end", "2026-06-30"])
    assert r.exit_code == 2 and "No look was used" in r.output
    ledger = ResearchLedger(Path(os.environ["TRADEMIND_LEDGER_DIR"]))
    assert ledger.looks("orb_momentum", (date(2026, 5, 1), date(2026, 10, 31))) == []


def test_backtest_split_option() -> None:
    args = ["backtest", "--start", "2026-04-20", "--end", "2026-04-24", "--split", "holdout"]
    r = CliRunner().invoke(app, args)
    assert r.exit_code == 2 and "research or forward" in r.output
