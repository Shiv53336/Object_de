"""Builders for hand-made test data."""

from __future__ import annotations

from datetime import date, time

import pandas as pd

from trademind.services.backtesting.dataset import prepare_symbol
from trademind.services.paper_broker.broker import Bar
from trademind.services.strategy_engine.view import BarView, DayFrames
from trademind.shared.clock import IST
from trademind.shared.config import AppConfig
from trademind.shared.enums import Segment, Side
from trademind.shared.models import Instrument, Order, Signal

DAY = date(2025, 9, 2)

STOCK = Instrument("AAA", "NSE", "stock", Segment.EQ_INTRADAY, 1, 0.05, True)
INDEX = Instrument("NIFTY 50", "NSE", "index", Segment.FUT, 75, 0.05, False)


def ts(hhmm: str, day: date = DAY) -> pd.Timestamp:
    h, m = hhmm.split(":")
    return pd.Timestamp.combine(day, time(int(h), int(m))).tz_localize(IST)


def bar(hhmm: str, o: float, h: float, lo: float, c: float) -> Bar:
    return Bar(ts(hhmm), o, h, lo, c)


def signal(
    side: Side = Side.LONG,
    stop: float = 95.0,
    target: float | None = 110.0,
    *,
    symbol: str = "AAA",
    strategy_id: str = "probe",
    timeframe: str = "5minute",
    at: str = "10:00",
    time_exit: time | None = None,
) -> Signal:
    return Signal(strategy_id, "1", timeframe, symbol, ts(at), side, stop, target, time_exit, {}, "test")


def order(sig: Signal, qty: int = 10, instrument: Instrument = STOCK, late: bool = False) -> Order:
    return Order(f"sig-{sig.instance_id}-{sig.symbol}", sig, qty, instrument, late)


def frames_for(
    base: pd.DataFrame, instrument: Instrument, cfg: AppConfig, day: date, timeframes: set[int]
) -> DayFrames:
    sd = prepare_symbol(instrument, base, cfg, timeframes)
    fr = sd.frames(day, cfg)
    assert fr is not None
    return fr


def view_at(fr: DayFrames, minutes: int, hhmm: str, market: BarView | None = None) -> BarView:
    df = fr.tf[minutes]
    row = int((df["ts"] == ts(hhmm, fr.ctx.day)).to_numpy().nonzero()[0][0])
    return BarView(fr, minutes, f"{minutes}minute", row, market)
