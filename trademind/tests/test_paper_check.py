"""Paper-vs-replay check (docs/TESTING.md step 5): bar and trade comparison, overlay source, end to end."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from tests.test_live import DAY, _instances, _live
from trademind.services.execution.paper_check import (
    OverlaySource,
    compare_bars,
    compare_trades,
    render,
    replay_day,
)
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.market_data.store import ParquetStore
from trademind.services.market_data.synthetic import SyntheticSource
from trademind.shared.clock import IST


def _bars(closes: list[float], volume: int = 100, start: str = "2025-09-03 09:15") -> pd.DataFrame:
    ts = pd.date_range(pd.Timestamp(start, tz=IST), periods=len(closes), freq="1min")
    return pd.DataFrame({"ts": ts, "open": closes, "high": closes, "low": closes, "close": closes,
                         "volume": [volume] * len(closes)})


def test_compare_bars_counts_missing_mismatch_and_volume() -> None:
    official = _bars([100.0, 101.0, 102.0, 103.0])
    live = _bars([100.0, 101.0, 102.5]).copy()  # last minute missing, third close off by 0.5
    live.loc[0, "volume"] = 50
    d = compare_bars("AAA", live, official, tick=0.05)
    assert (d.live_bars, d.official_bars, d.missing_live, d.extra_live) == (3, 4, 1, 0)
    assert d.ohlc_mismatch == 1
    assert d.max_close_diff_pct == pytest.approx(0.5 / 102 * 100)
    assert d.volume_diff_pct == pytest.approx((250 - 400) / 400 * 100)
    assert not d.ok  # volume 37.5% short


def test_compare_bars_ignores_sub_tick_noise() -> None:
    official = _bars([100.0, 101.0])
    d = compare_bars("AAA", _bars([100.01, 101.0]), official, tick=0.05)
    assert d.ohlc_mismatch == 0 and d.ok


def _trade(sym: str, minute: int, net: float, exit_reason: str = "TARGET") -> dict:
    t = pd.Timestamp("2025-09-03 09:30", tz=IST) + pd.Timedelta(minutes=minute)
    return {"instance_id": "orb@5minute", "symbol": sym, "side": "LONG", "entry_ts": t, "qty": 10,
            "entry_price": 100.0, "exit_ts": t + pd.Timedelta(minutes=20), "exit_price": 102.0,
            "exit_reason": exit_reason, "net_pnl": net}


def test_compare_trades_sorts_matches_changes_and_orphans() -> None:
    live = pd.DataFrame([_trade("AAA", 0, 20.0), _trade("BBB", 5, 15.0), _trade("CCC", 9, -5.0)])
    replay = pd.DataFrame([_trade("AAA", 0, 20.0), _trade("BBB", 5, -10.0, "STOP"), _trade("DDD", 7, 3.0)])
    d = compare_trades(live, replay)
    assert d.matched == 1 and not d.exact
    assert [r["symbol"] for r in d.changed] == ["BBB"]
    assert d.changed[0]["differences"]["exit_reason"] == ("TARGET", "STOP")
    assert [r["symbol"] for r in d.only_live] == ["CCC"]
    assert [r["symbol"] for r in d.only_replay] == ["DDD"]
    assert (d.live_net, d.replay_net) == (30.0, 13.0)


def test_compare_trades_empty_days_are_exact() -> None:
    assert compare_trades(pd.DataFrame(), pd.DataFrame()).exact


def test_overlay_replaces_only_the_chosen_day(tmp_path) -> None:
    store = ParquetStore(tmp_path)
    store.write("AAA", "1minute", pd.concat([_bars([1.0, 2.0], start="2025-09-02 09:15"),
                                              _bars([3.0, 4.0], start="2025-09-03 09:15")]))
    new_day = _bars([9.0, 9.0, 9.0], start="2025-09-03 09:15")
    overlay = OverlaySource(store, date(2025, 9, 3), {"AAA": new_day})
    out = overlay.get_bars("AAA", "1minute", date(2025, 9, 2), date(2025, 9, 3))
    assert out["close"].tolist() == [1.0, 2.0, 9.0, 9.0, 9.0]
    assert overlay.get_bars("BBB", "1minute", date(2025, 9, 2), date(2025, 9, 3)).empty


@pytest.fixture(scope="module")
def live_day(small_cfg, tmp_path_factory):
    """A live paper day driven by ticks (as in test_live), with its bars persisted to the store."""
    s = small_cfg.settings
    src = SyntheticSource(11, build_instruments(s), s.session, s.market_symbol)
    store = ParquetStore(tmp_path_factory.mktemp("bars"))
    for sym in build_instruments(s):
        store.write(sym, "1minute", src.get_bars(sym, "1minute", DAY - timedelta(days=s.backtest.warmup_days),
                                                 DAY - timedelta(days=1)))
    trades, _, _ = _live(small_cfg, src, store, tmp_path_factory.mktemp("live"))
    return src, store, trades


def test_replay_on_live_bars_matches_the_live_run(small_cfg, live_day) -> None:
    _, store, live_trades = live_day
    replay = replay_day(small_cfg, store, DAY, strategies=_instances())
    d = compare_trades(live_trades, replay)
    assert len(live_trades) >= 5
    assert d.exact and d.matched == len(live_trades)
    assert "Verdict: PASS" in render(DAY, "run1", [], d, None, [])


def test_replay_on_different_bars_shows_differences(small_cfg, live_day) -> None:
    src, store, live_trades = live_day
    shifted = src.get_bars("AAA", "1minute", DAY, DAY)
    shifted[["open", "high", "low", "close"]] *= 1.004
    replay = replay_day(small_cfg, OverlaySource(store, DAY, {"AAA": shifted}), DAY, strategies=_instances())
    d = compare_trades(live_trades, replay)
    assert not d.exact
    assert "Verdict: FAIL" in render(DAY, "run1", [], d, d, [])
