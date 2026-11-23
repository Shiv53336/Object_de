"""Live paper reliability: dead streams, gap filling, restarts, early stops and quote capture."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest

from tests.test_live import DAY, KEY, _backtest, _instances, _same, _ticks_for_minute
from trademind.database.journal import Journal
from trademind.services.execution.live_paper import LivePaperRunner
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.market_data.store import ParquetStore
from trademind.services.market_data.synthetic import SyntheticSource
from trademind.services.notify.telegram import Notifier
from trademind.shared.clock import session_grid
from trademind.shared.exceptions import DataError

ONE, GRACE = pd.Timedelta(minutes=1), pd.Timedelta(seconds=5)


@pytest.fixture(scope="module")
def market(small_cfg, tmp_path_factory):
    s = small_cfg.settings
    src = SyntheticSource(11, build_instruments(s), s.session, s.market_symbol)
    store = ParquetStore(tmp_path_factory.mktemp("bars"))
    for sym in build_instruments(s):
        store.write(sym, "1minute", src.get_bars(sym, "1minute", DAY - timedelta(days=s.backtest.warmup_days),
                                                 DAY - timedelta(days=1)))
    return src, store


class Recorder(Notifier):
    def __init__(self) -> None:
        super().__init__(token="", chat_id="")
        self.messages: list[str] = []

    def send(self, text: str) -> bool:
        self.messages.append(text)
        return True


def _runner(cfg, store, tmp_path, **kw) -> LivePaperRunner:
    j = Journal(f"sqlite:///{tmp_path / 'live.sqlite'}")
    return LivePaperRunner(cfg, store, j, _instances(), DAY, grace_seconds=5,
                           live_store=ParquetStore(tmp_path / "bars_live"), **kw)


def _drive(runner, day_bars, silent: range, poll_every_minute: bool = True) -> None:
    """Feed ticks minute by minute, except during `silent` (the stream is dead)."""
    stamps = session_grid(DAY, runner.session.open, runner.session.close, 1)
    cum: dict[str, int] = {}
    for g in range(len(stamps)):
        if g in silent:
            for sym, df in day_bars.items():  # the exchange's cumulative volume keeps growing
                if not sym.startswith("NIFTY"):
                    cum[sym] = cum.get(sym, 0) + int(df["volume"].iloc[g])
        else:
            runner.on_ticks(_ticks_for_minute(day_bars, g, cum))
        if poll_every_minute:
            runner.poll(stamps[g] + ONE + GRACE)
    assert runner.finished


def test_dead_stream_is_filled_from_candles_and_keeps_parity(small_cfg, market, tmp_path) -> None:
    src, store = market
    rec = Recorder()

    def fetch(symbols, start, now):
        return {s: src.get_bars(s, "1minute", DAY, DAY) for s in symbols}

    runner = _runner(small_cfg, store, tmp_path, notifier=rec, fetch_minutes=fetch)
    day_bars = {s: src.get_bars(s, "1minute", DAY, DAY) for s in runner._today}
    _drive(runner, day_bars, silent=range(60, 80))
    assert runner.stalls == 1 and runner.filled_minutes >= 19 and runner.empty_minutes == 0
    assert any("no market data since" in m for m in rec.messages)
    assert any("market data back" in m for m in rec.messages)
    live = runner.journal.read_trades(runner.run_id)
    bt_trades, _ = _backtest(small_cfg, src, tmp_path)
    _same(bt_trades, live, KEY, ["instance_id", "symbol", "entry_ts"])


def test_dead_stream_without_candles_waits_then_records_the_gap(small_cfg, market, tmp_path) -> None:
    src, store = market
    rec = Recorder()
    runner = _runner(small_cfg, store, tmp_path, notifier=rec, give_up_minutes=5)
    day_bars = {s: src.get_bars(s, "1minute", DAY, DAY) for s in runner._today}
    stamps = session_grid(DAY, runner.session.open, runner.session.close, 1)
    cum: dict[str, int] = {}
    for g in range(30):
        runner.on_ticks(_ticks_for_minute(day_bars, g, cum))
        runner.poll(stamps[g] + ONE + GRACE)
    assert runner.next_g == 30
    runner.poll(stamps[32] + ONE + GRACE)  # three silent minutes: stalled, nothing processed
    assert runner.stalled and runner.next_g == 30
    runner.poll(stamps[36] + ONE + GRACE)  # past give_up_minutes: carries on with empty minutes
    assert runner.gave_up and runner.next_g == 37 and runner.empty_minutes == 7
    assert any("carrying on" in m for m in rec.messages)
    runner.finish()
    run = runner.journal.get_run(runner.run_id)
    assert run["status"] == "done" and "empty_minutes=7" in run["notes"]


def test_restart_supersedes_and_a_finished_day_is_not_rerun(small_cfg, market, tmp_path) -> None:
    _, store = market
    first = _runner(small_cfg, store, tmp_path)
    second = _runner(small_cfg, store, tmp_path)
    assert second.journal.get_run(first.run_id)["status"] == "superseded"
    second.finish()
    assert second.journal.get_run(second.run_id)["status"] == "done"
    with pytest.raises(DataError, match="already finished"):
        _runner(small_cfg, store, tmp_path)


def test_stopped_day_does_not_count(small_cfg, market, tmp_path) -> None:
    _, store = market
    rec = Recorder()
    runner = _runner(small_cfg, store, tmp_path, notifier=rec)
    runner.finish(status="stopped")
    assert runner.journal.get_run(runner.run_id)["status"] == "stopped"
    assert runner.journal.read_runs_between(DAY, DAY, "live").empty
    assert "does not count" in rec.messages[-1]


def test_quotes_are_kept_per_minute(small_cfg, market, tmp_path) -> None:
    _, store = market
    runner = _runner(small_cfg, store, tmp_path)
    t0 = session_grid(DAY, runner.session.open, runner.session.close, 1)[0]
    runner.on_ticks([("AAA", t0 + pd.Timedelta(seconds=1), 100.0, 10, 99.9, 100.1),
                     ("AAA", t0 + pd.Timedelta(seconds=50), 100.4, 20, 100.3, 100.5),
                     ("AAA", t0 + pd.Timedelta(seconds=61), 100.6, 30, 100.5, 100.7),
                     ("BBB", t0 + pd.Timedelta(seconds=2), 50.0, 5, None, None)])
    runner.finish(status="stopped")
    q = runner.journal.read_quotes(runner.run_id)
    assert q["symbol"].tolist() == ["AAA", "AAA"]
    first = q.iloc[0]
    assert (first["first_bid"], first["first_ask"], first["last_bid"], first["last_ask"]) == (
        99.9, 100.1, 100.3, 100.5)
