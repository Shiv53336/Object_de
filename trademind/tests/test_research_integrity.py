"""Honest statistics (DECISIONS D29): research ledger, fixed holdout window, day-block bootstrap,
run coverage, schema migrations (T06) and the scoreboard's cost columns."""

from __future__ import annotations

import dataclasses
import subprocess
from datetime import date

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, inspect

from trademind.database import models as m
from trademind.database.journal import BASELINE, Journal, _alembic_config, migrate
from trademind.services.backtesting.runner import check_split
from trademind.services.learning.ledger import Hypothesis, LedgerError, ResearchLedger
from trademind.services.learning.metrics import scoreboard
from trademind.services.learning.validation import (
    bootstrap_lower_bound,
    day_block_lower_bound,
    session_coverage,
)
from trademind.shared.clock import IST
from trademind.shared.config import AppConfig
from trademind.shared.exceptions import HoldoutAccessError

H = Hypothesis("orb_momentum", "1", "5minute", "abc")
WINDOW = (date(2026, 5, 1), date(2026, 10, 31))


# ---- ledger --------------------------------------------------------------------------------
def test_ledger_counts_distinct_real_hypotheses_only(tmp_path) -> None:
    led = ResearchLedger(tmp_path)
    kw = {"run_id": "r1", "period_start": date(2025, 5, 1), "period_end": date(2026, 4, 30)}
    assert led.record_hypothesis(H, source="parquet", **kw)
    assert not led.record_hypothesis(H, source="parquet", **kw)  # rerun
    assert not led.record_hypothesis(dataclasses.replace(H, params_hash="zzz"), source="synthetic", **kw)
    assert led.record_hypothesis(dataclasses.replace(H, timeframe="15minute"), source="kite", **kw)
    assert led.distinct_hypotheses() == 2


def test_ledger_looks_are_per_strategy_and_window(tmp_path) -> None:
    led = ResearchLedger(tmp_path)
    kw = {"period": WINDOW, "research_run_id": "r", "holdout_run_id": "h", "passed": False,
          "source": "parquet"}
    led.record_look(H, window=WINDOW, **kw)
    led.record_look(dataclasses.replace(H, version="2", timeframe="15minute"), window=WINDOW, **kw)
    led.record_look(H, window=(date(2027, 1, 1), date(2027, 6, 30)), **kw)
    assert len(led.looks("orb_momentum", WINDOW)) == 2
    assert led.looks("sweep_reversal", WINDOW) == []


def test_ledger_fails_closed_on_a_damaged_line(tmp_path) -> None:
    (tmp_path / "holdout_looks.jsonl").write_text('{"strategy_id": "x"}\nnot json\n', encoding="utf-8")
    with pytest.raises(LedgerError, match="not valid JSON"):
        ResearchLedger(tmp_path).looks("x", WINDOW)


def test_ledger_knows_when_it_is_not_committed(tmp_path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=tmp_path,
                       check=True, capture_output=True)

    led = ResearchLedger(tmp_path / "ledger")
    assert led.uncommitted() is None  # not a git checkout
    git("init", "-q")
    led.record_hypothesis(H, run_id="r", period_start=date(2025, 5, 1), period_end=date(2026, 4, 30),
                          source="parquet")
    assert led.uncommitted() is True
    git("add", ".")
    git("commit", "-qm", "ledger")
    assert led.uncommitted() is False


# ---- data splits ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "split,start,end,error",
    [
        ("research", "2026-04-01", "2026-05-01", HoldoutAccessError),
        ("holdout", "2026-04-30", "2026-05-10", ValueError),
        ("holdout", "2026-10-20", "2026-11-03", ValueError),
        ("forward", "2026-10-31", "2026-11-05", HoldoutAccessError),
        ("replay", "2026-06-01", "2026-06-01", HoldoutAccessError),
        ("sideways", "2026-11-02", "2026-11-03", ValueError),
    ],
)
def test_splits_keep_out_of_the_holdout(cfg: AppConfig, split, start, end, error) -> None:
    with pytest.raises(error):
        check_split(cfg, date.fromisoformat(start), date.fromisoformat(end), split)


@pytest.mark.parametrize("split,start,end", [("research", "2025-05-01", "2026-04-30"),
                                             ("holdout", "2026-05-01", "2026-10-31"),
                                             ("forward", "2026-11-02", "2026-11-20")])
def test_splits_allow_their_own_periods(cfg: AppConfig, split, start, end) -> None:
    check_split(cfg, date.fromisoformat(start), date.fromisoformat(end), split)


def test_live_paper_refuses_holdout_days(small_cfg: AppConfig, tmp_path) -> None:
    from trademind.services.execution.live_paper import LivePaperRunner
    from trademind.services.market_data.store import ParquetStore

    with pytest.raises(HoldoutAccessError):
        LivePaperRunner(small_cfg, ParquetStore(tmp_path), Journal(f"sqlite:///{tmp_path}/j.sqlite"), [],
                        date(2026, 6, 1))


# ---- statistics ------------------------------------------------------------------------
def test_day_block_bound_is_wider_when_trades_cluster_by_day() -> None:
    rng = np.random.default_rng(3)
    day_effects = rng.normal(0.2, 1.0, 50)
    r = np.repeat(day_effects, 4)  # four trades a day that move together
    days = np.repeat(np.arange(50), 4)
    naive = bootstrap_lower_bound(r, 0.95, 4000, 7)
    blocked = day_block_lower_bound(r, days, 0.95, 4000, 7)
    assert blocked < naive
    independent = day_block_lower_bound(r, np.arange(200), 0.95, 4000, 7)
    assert independent == pytest.approx(naive, abs=0.02)


def test_session_coverage_counts_weekdays() -> None:
    assert session_coverage(5, date(2025, 1, 6), date(2025, 1, 12)) == 1.0  # Mon..Sun
    assert session_coverage(4, date(2025, 1, 6), date(2025, 1, 10)) == pytest.approx(0.8)
    assert session_coverage(None, date(2025, 1, 6), date(2025, 1, 10)) == 0.0


# ---- journal ---------------------------------------------------------------------------
def _schema(engine) -> dict[str, set[str]]:
    insp = inspect(engine)
    tables = [t for t in insp.get_table_names() if t != "alembic_version"]
    return {t: {c["name"] for c in insp.get_columns(t)} for t in tables}


def test_migrations_build_the_same_schema_as_the_models(tmp_path) -> None:
    from alembic import command

    by_models = create_engine(f"sqlite:///{tmp_path}/a.sqlite")
    m.metadata.create_all(by_models)
    by_migrations = create_engine(f"sqlite:///{tmp_path}/b.sqlite")
    with by_migrations.begin() as cx:
        command.upgrade(_alembic_config(cx), "head")
    assert _schema(by_migrations) == _schema(by_models)


def test_old_databases_are_upgraded_in_place(tmp_path) -> None:
    from alembic import command

    eng = create_engine(f"sqlite:///{tmp_path}/old.sqlite")
    with eng.begin() as cx:
        command.upgrade(_alembic_config(cx), BASELINE)
        cx.exec_driver_sql("DROP TABLE alembic_version")  # as created before migrations existed
    assert "n_sessions" not in _schema(eng)["runs"]
    assert migrate(eng) == "upgraded"
    assert {"n_sessions", "first_session", "last_session"} <= _schema(eng)["runs"]
    assert "quotes" in _schema(eng)
    assert migrate(eng) == "current"


def test_research_run_must_match_version_params_config_and_source(tmp_path) -> None:
    j = Journal(f"sqlite:///{tmp_path}/j.sqlite")
    inst = "orb_momentum@5minute"

    def run(source: str, chash: str, params: dict) -> str:
        rid = j.start_run(mode="backtest", data_split="research", period_start=date(2025, 5, 1),
                          period_end=date(2025, 5, 2), config_hash=chash, source=source, instances=[inst])
        j.log_trial(run_id=rid, strategy_id="orb_momentum", strategy_version="1", timeframe="5minute",
                    params=params, data_split="research", period_start=date(2025, 5, 1),
                    period_end=date(2025, 5, 2), n_trades=0, expectancy_r=None)
        j.finish_run(rid, status="done", n_signals=0, n_trades=0, sessions=[date(2025, 5, 1)])
        return rid

    from trademind.database.journal import params_hash

    good = run("parquet", "cfg1", {"a": 1})
    run("synthetic", "cfg1", {"a": 1})
    run("parquet", "cfg2", {"a": 1})
    run("parquet", "cfg1", {"a": 2})
    real = frozenset({"parquet"})
    found = j.find_research_run(inst, "1", params_hash({"a": 1}), "cfg1", real)
    assert found["run_id"] == good and found["n_sessions"] == 1
    assert j.find_research_run(inst, "1", params_hash({"a": 3}), "cfg1", real) is None
    assert j.find_research_run(inst, "2", params_hash({"a": 1}), "cfg1", real) is None


# ---- scoreboard ------------------------------------------------------------------------
def test_scoreboard_shows_gross_and_cost_in_r_and_period_breakdown() -> None:
    entries = pd.to_datetime(["2025-01-02 10:00", "2025-04-02 10:00", "2025-04-03 10:00", "2025-07-01 10:00"])
    t = pd.DataFrame({
        "instance_id": ["a"] * 4, "trade_id": list("1234"), "qty": [100] * 4, "risk_per_unit": [10.0] * 4,
        "gross_pnl": [1000.0, -1000.0, -1000.0, 2000.0], "costs": [100.0] * 4,
        "net_pnl": [900.0, -1100.0, -1100.0, 1900.0], "r_multiple": [0.9, -1.1, -1.1, 1.9],
        "exit_reason": ["TARGET", "STOP", "STOP", "TARGET"], "mfe_r": [1.0, 0.2, 0.6, 2.0],
        "target": [1.0] * 4, "entry_ts": entries.tz_localize(IST), "exit_ts": entries.tz_localize(IST),
        "context": [{}] * 4,
    })
    row = scoreboard(t, 2).iloc[0]
    assert (row["gross_expectancy_r"], row["cost_per_trade_r"], row["expectancy_r"]) == pytest.approx(
        (0.25, 0.10, 0.15))
    by_q = scoreboard(t, 1, "quarter")
    assert by_q["quarter"].tolist() == ["2025Q1", "2025Q2", "2025Q3"]
    assert by_q["n_trades"].tolist() == [1, 2, 1]
