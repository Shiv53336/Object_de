from __future__ import annotations

from datetime import date, datetime, timedelta

import httpx
import pandas as pd
import pytest

from trademind.database.journal import Journal
from trademind.services.backtesting.runner import run_backtest
from trademind.services.execution.kite_stream import convert_tick
from trademind.services.execution.live_paper import LivePaperRunner
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.market_data.store import ParquetStore
from trademind.services.market_data.synthetic import SyntheticSource
from trademind.services.notify.telegram import Notifier
from trademind.services.strategy_engine.base import Strategy
from trademind.services.strategy_engine.equity.orb_momentum import OrbMomentum
from trademind.services.strategy_engine.equity.sweep_reversal import SweepReversal
from trademind.services.strategy_engine.view import BarView
from trademind.shared.clock import IST, session_grid
from trademind.shared.config import AppConfig
from trademind.shared.enums import Side
from trademind.shared.exceptions import DataError
from trademind.shared.models import Signal

DAY = date(2025, 9, 3)
KEY = ["instance_id", "symbol", "side", "qty", "signal_ts", "entry_ts", "entry_price", "exit_ts",
       "exit_price", "exit_reason", "net_pnl", "r_multiple", "mfe_r", "mae_r", "post_exit_mfe_r"]
SIG_KEY = ["instance_id", "symbol", "ts", "side", "stop", "target", "approved", "reject_reason", "qty"]


class Every30(Strategy):
    """Signals often, so the parity test always has trades, rejections and stops."""

    id = "every30"
    version = "1"
    scope = "all"

    def on_bar(self, view: BarView) -> list[Signal]:
        if view.now.minute % 30:
            return []
        c = float(view.bar["close"])
        side = Side.LONG if view.now.hour % 2 else Side.SHORT
        off = c * 0.002
        stop, tgt = (c - off, c + 2 * off) if side == Side.LONG else (c + off, c - 2 * off)
        return [self.signal(view, side, stop, tgt, "every30")]


def _instances() -> list[Strategy]:
    return [OrbMomentum("5minute"), SweepReversal("5minute"), Every30("5minute"), Every30("15minute")]


@pytest.fixture(scope="module")
def market(small_cfg: AppConfig, tmp_path_factory) -> tuple[SyntheticSource, ParquetStore]:
    s = small_cfg.settings
    src = SyntheticSource(11, build_instruments(s), s.session, s.market_symbol)
    store = ParquetStore(tmp_path_factory.mktemp("bars"))
    start = DAY - timedelta(days=s.backtest.warmup_days)
    for sym in build_instruments(s):
        store.write(sym, "1minute", src.get_bars(sym, "1minute", start, DAY - timedelta(days=1)))
    return src, store


def _ticks_for_minute(day_bars: dict[str, pd.DataFrame], g: int, cum: dict[str, int]) -> list:
    out = []
    for sym, df in day_bars.items():
        r = df.iloc[g]
        t0 = r["ts"]
        vol = int(r["volume"])
        has_vol = not sym.startswith("NIFTY")  # index ticks carry no volume
        c0 = cum.get(sym, 0)
        c = (lambda x: x) if has_vol else (lambda x: None)
        out += [
            (sym, t0 + pd.Timedelta(seconds=0), float(r["open"]), c(c0)),
            (sym, t0 + pd.Timedelta(seconds=15), float(r["high"]), c(c0)),
            (sym, t0 + pd.Timedelta(seconds=30), float(r["low"]), c(c0)),
            (sym, t0 + pd.Timedelta(seconds=45), float(r["close"]), c(c0 + vol)),
        ]
        cum[sym] = c0 + vol
    return out


def _backtest(cfg, src, tmp_path):
    j = Journal(f"sqlite:///{tmp_path / 'bt.sqlite'}")
    rid = run_backtest(cfg, src, DAY, DAY, j, strategies=_instances())
    return j.read_trades(rid), j.read_signals(rid)


def _live(cfg, src, store, tmp_path, backfill_minutes: int = 0):
    j = Journal(f"sqlite:///{tmp_path / 'live.sqlite'}")
    runner = LivePaperRunner(cfg, store, j, _instances(), DAY, grace_seconds=5,
                             live_store=ParquetStore(tmp_path / "bars_live"))
    syms = list(runner._today)
    day_bars = {s: src.get_bars(s, "1minute", DAY, DAY) for s in syms}
    stamps = session_grid(DAY, cfg.settings.session.open, cfg.settings.session.close, 1)
    one, grace = pd.Timedelta(minutes=1), pd.Timedelta(seconds=5)
    cum: dict[str, int] = {}
    if backfill_minutes:
        now = stamps[backfill_minutes] + pd.Timedelta(seconds=20)
        n = runner.backfill(day_bars, now)
        assert n == backfill_minutes * len(syms)
        for s in syms:
            cum[s] = int(day_bars[s]["volume"].iloc[:backfill_minutes].sum())
        runner.poll(now)
    for g in range(backfill_minutes, len(stamps)):
        runner.on_ticks(_ticks_for_minute(day_bars, g, cum))
        runner.poll(stamps[g] + one + grace)
    assert runner.finished
    rid = runner.run_id
    return j.read_trades(rid), j.read_signals(rid), runner


def _same(a: pd.DataFrame, b: pd.DataFrame, cols: list[str], by: list[str]) -> None:
    a = a[cols].sort_values(by).reset_index(drop=True)
    b = b[cols].sort_values(by).reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_live_replay_matches_backtest(small_cfg, market, tmp_path) -> None:
    src, store = market
    bt_trades, bt_sigs = _backtest(small_cfg, src, tmp_path)
    lv_trades, lv_sigs, runner = _live(small_cfg, src, store, tmp_path)
    assert len(bt_trades) >= 5 and (bt_trades["exit_reason"] == "STOP").any()
    _same(bt_trades, lv_trades, KEY, ["instance_id", "symbol", "entry_ts"])
    _same(bt_sigs, lv_sigs, SIG_KEY, ["instance_id", "symbol", "ts"])
    # today's tick-built bars go to the live store, never into the research store
    assert len(runner.live_store.read("AAA", "1minute", DAY, DAY)) == 375
    assert store.read("AAA", "1minute", DAY, DAY).empty


def test_late_start_with_backfill_matches_backtest(small_cfg, market, tmp_path) -> None:
    src, store = market
    bt_trades, _ = _backtest(small_cfg, src, tmp_path)
    lv_trades, _, _ = _live(small_cfg, src, store, tmp_path, backfill_minutes=100)
    _same(bt_trades, lv_trades, KEY, ["instance_id", "symbol", "entry_ts"])


def test_runner_needs_history(small_cfg, tmp_path) -> None:
    j = Journal(f"sqlite:///{tmp_path / 'x.sqlite'}")
    with pytest.raises(DataError, match="data download"):
        LivePaperRunner(small_cfg, ParquetStore(tmp_path / "empty"), j, _instances(), DAY)


def test_convert_tick() -> None:
    received = pd.Timestamp("2025-09-03 10:00:07", tz=IST)
    m = {256265: "NIFTY 50", 738561: "RELIANCE"}
    t = convert_tick({"instrument_token": 738561, "last_price": 2500.5, "volume_traded": 1200,
                      "exchange_timestamp": datetime(2025, 9, 3, 10, 0, 5)}, m, received)
    assert t == ("RELIANCE", pd.Timestamp("2025-09-03 10:00:05", tz=IST), 2500.5, 1200, None, None)
    idx = convert_tick({"instrument_token": 256265, "last_price": 24000.0}, m, received)
    assert idx == ("NIFTY 50", received, 24000.0, None, None, None)
    full = convert_tick({"instrument_token": 738561, "last_price": 2500.5,
                         "depth": {"buy": [{"price": 2500.4, "quantity": 10}],
                                   "sell": [{"price": 2500.6, "quantity": 7}]}}, m, received)
    assert full[-2:] == (2500.4, 2500.6)
    assert convert_tick({"instrument_token": 1, "last_price": 1.0}, m, received) is None


# ---- notifier ------------------------------------------------------------------------------


def test_notifier_noop_without_credentials() -> None:
    n = Notifier(token="", chat_id="")
    assert not n.enabled and n.send("hi") is False


def test_notifier_sends_and_never_raises() -> None:
    seen: list[httpx.Request] = []

    def ok(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    n = Notifier("T", "42", client=httpx.Client(transport=httpx.MockTransport(ok)))
    assert n.trade_opened("orb_momentum@5minute", "INFY", "LONG", 10, 1500.0, 1490.0, 1520.0)
    assert seen[0].url.path == "/botT/sendMessage" and b'"chat_id":"42"' in seen[0].content.replace(b" ", b"")

    def boom(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    bad = Notifier("T", "42", client=httpx.Client(transport=httpx.MockTransport(boom)))
    assert bad.error("x") is False


def test_telegram_login_flow() -> None:
    calls: list[str] = []
    replies = iter([
        {"ok": True, "result": [{"update_id": 5, "message": {"chat": {"id": 42}, "text": "old"}}]},
        {"ok": True, "result": [
            {"update_id": 6, "message": {"chat": {"id": 999}, "text": "request_token=STRANGER1"}},
            {"update_id": 7, "message": {"chat": {"id": 42},
                                         "text": "https://127.0.0.1/?action=login&request_token=Abc123XYZ&status=success"}},
        ]},
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path} {request.url.query.decode()}")
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(200, json=next(replies))
        return httpx.Response(200, json={"ok": True})

    n = Notifier("T", "42", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert n.wait_for_request_token("https://kite/login") == "Abc123XYZ"
    assert calls[0].endswith("timeout=0") and "sendMessage" in calls[1] and "offset=6" in calls[2]


def test_telegram_login_times_out() -> None:
    t = [0.0]

    def clock() -> float:
        t[0] += 1000
        return t[0]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": []})

    n = Notifier("T", "42", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert n.wait_for_request_token("https://kite/login", timeout_s=1500, clock=clock) is None
