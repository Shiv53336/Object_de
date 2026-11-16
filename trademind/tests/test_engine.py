from __future__ import annotations

from datetime import date, time

import pandas as pd
import pytest

from trademind.database.journal import Journal
from trademind.services.backtesting.runner import run_backtest
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.market_data.source import empty_bars
from trademind.services.market_data.synthetic import SyntheticSource, make_session
from trademind.services.strategy_engine.base import Strategy
from trademind.services.strategy_engine.view import BarView
from trademind.shared.config import AppConfig
from trademind.shared.enums import RejectReason, Side
from trademind.shared.exceptions import HoldoutAccessError
from trademind.shared.models import Signal

START, END = date(2025, 9, 1), date(2025, 9, 5)


class Probe(Strategy):
    """Asserts the no-lookahead contract on every call; goes long on stocks at one bar."""

    id = "probe"
    version = "1"
    scope = "all"

    def __init__(self, timeframe: str = "5minute", fire_at: time = time(10, 0),
                 stop_off: float = 0.1, target_off: float | None = None) -> None:
        super().__init__(timeframe)
        self.fire_at, self.stop_off, self.target_off = fire_at, stop_off, target_off
        self.seen: list[pd.Timestamp] = []

    def on_bar(self, view: BarView) -> list[Signal]:
        assert view.bars["ts"].max() == view.now
        assert view.base.empty or view.base["ts"].max() < view.close_time
        assert view.market is None or view.market.now == view.now
        if view.instrument.kind == "stock" and view.symbol == "AAA":
            self.seen.append(view.now)
        if view.now.time() != self.fire_at or view.instrument.kind != "stock" or self.emitted(view.symbol):
            return []
        c = float(view.bar["close"])
        tgt = None if self.target_off is None else c + self.target_off
        stop = c * (1 - self.stop_off) if self.stop_off < 1 else c - self.stop_off
        return [self.signal(view, Side.LONG, stop, tgt, "probe")]


class Spammer(Strategy):
    id = "spammer"
    version = "1"
    scope = "stocks"

    def on_bar(self, view: BarView) -> list[Signal]:
        c = float(view.bar["close"])
        return [self.signal(view, Side.LONG, c * 0.99, c * 1.02, "spam")]


def _journal(tmp_path) -> Journal:
    return Journal(f"sqlite:///{tmp_path / 'j.sqlite'}")


def _synth(cfg: AppConfig) -> SyntheticSource:
    s = cfg.settings
    return SyntheticSource(7, build_instruments(s), s.session, s.market_symbol)


def _run(cfg, tmp_path, strategies, start=START, end=END, source=None):
    j = _journal(tmp_path)
    rid = run_backtest(cfg, source or _synth(cfg), start, end, j, strategies=strategies)
    return j, rid


KEY_COLS = ["instance_id", "symbol", "side", "qty", "entry_ts", "entry_price", "exit_ts",
            "exit_price", "exit_reason", "net_pnl", "r_multiple", "mfe_r", "mae_r"]


def test_probe_trades_enter_next_base_bar_and_square_off(small_cfg, tmp_path) -> None:
    j, rid = _run(small_cfg, tmp_path, [Probe()])
    t = j.read_trades(rid)
    assert len(t) == 2 * 5  # two stocks, five sessions
    assert (t["signal_ts"].dt.strftime("%H:%M") == "10:00").all()
    assert (t["entry_ts"].dt.strftime("%H:%M") == "10:05").all()
    assert (t["exit_reason"] == "SQUAREOFF").all()
    assert (t["exit_ts"].dt.strftime("%H:%M") == "15:20").all()
    run = j.get_run(rid)
    assert run["status"] == "done" and run["n_trades"] == 10


def test_fifteen_minute_instance_sees_only_15m_closes(small_cfg, tmp_path) -> None:
    p = Probe("15minute", fire_at=time(10, 15))
    j, rid = _run(small_cfg, tmp_path, [p], end=START)
    assert len(p.seen) == 25 and all(ts.minute % 15 == 0 for ts in p.seen)
    t = j.read_trades(rid)
    assert (t["entry_ts"].dt.strftime("%H:%M") == "10:30").all()


def test_backtest_is_deterministic(small_cfg, tmp_path) -> None:
    j1, r1 = _run(small_cfg, tmp_path / "a", [Probe(), Spammer("5minute")])
    j2, r2 = _run(small_cfg, tmp_path / "b", [Probe(), Spammer("5minute")])
    pd.testing.assert_frame_equal(j1.read_trades(r1)[KEY_COLS], j2.read_trades(r2)[KEY_COLS])


def test_truncation_invariance(small_cfg, tmp_path) -> None:
    j1, r1 = _run(small_cfg, tmp_path / "a", [Spammer("5minute")], end=date(2025, 9, 3))
    j2, r2 = _run(small_cfg, tmp_path / "b", [Spammer("5minute")], end=date(2025, 9, 10))
    short = j1.read_trades(r1)[KEY_COLS]
    long = j2.read_trades(r2)
    long = long[long["exit_ts"].dt.date <= date(2025, 9, 3)][KEY_COLS].reset_index(drop=True)
    pd.testing.assert_frame_equal(short, long)


def test_risk_limits_hold_end_to_end(small_cfg, tmp_path) -> None:
    j, rid = _run(small_cfg, tmp_path, [Spammer("5minute")])
    s = j.read_signals(rid)
    assert (s["approved"].groupby(s["ts"].dt.date).sum() <= 3).all()
    reasons = set(s["reject_reason"].dropna())
    assert reasons <= {str(r) for r in RejectReason}
    assert "position_exists" in reasons or "max_open_positions" in reasons


def test_research_run_cannot_touch_holdout(small_cfg, tmp_path) -> None:
    with pytest.raises(HoldoutAccessError):
        _run(small_cfg, tmp_path, [Probe()], start=date(2026, 4, 27), end=date(2026, 5, 1))


def test_journal_contents(small_cfg, tmp_path) -> None:
    j, rid = _run(small_cfg, tmp_path, [Probe()])
    t = j.read_trades(rid)
    ctx = t["context"].iloc[0]
    assert {"gap_bucket", "day_type", "time_bucket", "timeframe", "or_width_bucket"} <= set(ctx)
    assert str(t["entry_ts"].dt.tz) == "Asia/Kolkata"
    s = j.read_signals(rid)
    assert len(s) == 10 and s["approved"].all()
    with j.engine.connect() as cx:
        n_ctx = cx.exec_driver_sql("select count(*) from day_context").scalar_one()
        n_trials = cx.exec_driver_sql("select count(*) from trials").scalar_one()
    assert n_ctx == 4 * 5 and n_trials == 1


class DictSource:
    def __init__(self, bars: dict[str, pd.DataFrame]) -> None:
        self.bars = bars

    def get_bars(self, symbol, interval, start, end):
        df = self.bars.get(symbol)
        return df.copy() if df is not None else empty_bars()


def test_trap_diagnostics_after_stop(small_cfg, tmp_path) -> None:
    s = small_cfg.settings.session
    day = date(2025, 9, 2)
    closes = [100.0] * 50 + [99.5, 98.9] + [100 + k * 0.1 for k in range(30)]
    closes += [103.0] * (375 - len(closes))
    src = DictSource({
        "NIFTY 50": make_session(day, [24000.0] * 375, s),
        "AAA": make_session(day, closes, s),
    })
    j, rid = _run(small_cfg, tmp_path, [Probe(stop_off=1.0, target_off=2.0)],
                  start=day, end=day, source=src)
    (t,) = j.read_trades(rid).to_dict("records")
    assert t["exit_reason"] == "STOP"
    assert t["entry_ts"].strftime("%H:%M") == "10:05"
    assert t["target_hit_after_stop"] is True or t["target_hit_after_stop"] == 1
    entry = 100 * 1.0003
    assert t["post_exit_mfe_r"] == pytest.approx((103 * 1.0005 - entry) / (entry - 99.0))
