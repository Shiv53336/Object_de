"""Instrument registry (BLUEPRINT 5.2). Phase 0-4: built from config; later refreshed from Kite."""

from __future__ import annotations

from trademind.shared.config import Settings
from trademind.shared.enums import Segment
from trademind.shared.models import Instrument


def build_instruments(
    settings: Settings, overrides: dict[str, tuple[int, float]] | None = None
) -> dict[str, Instrument]:
    """Instruments from config. `overrides` maps symbol -> (lot_size, tick_size) from the broker."""
    out: dict[str, Instrument] = {}
    for ic in settings.universe.indices:
        out[ic.symbol] = Instrument(
            symbol=ic.symbol,
            exchange=ic.exchange,
            kind="index",
            trade_segment=Segment.FUT,  # PLAN 4.4: index trades simulated as a future
            lot_size=ic.lot_size,
            tick_size=ic.tick_size,
            has_volume=False,
        )
    for ic in settings.universe.stocks:
        out[ic.symbol] = Instrument(
            symbol=ic.symbol,
            exchange=ic.exchange,
            kind="stock",
            trade_segment=Segment.EQ_INTRADAY,
            lot_size=1,
            tick_size=ic.tick_size,
            has_volume=True,
        )
    for sym, (lot, tick) in (overrides or {}).items():
        if sym in out:
            i = out[sym]
            out[sym] = Instrument(i.symbol, i.exchange, i.kind, i.trade_segment, lot, tick, i.has_volume)
    return out
