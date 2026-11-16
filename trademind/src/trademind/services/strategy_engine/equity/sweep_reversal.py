"""STRATEGIES C.6 `sweep_reversal` v1: trade the failed stop run at yesterday's high or low.

If both sides qualify on the same bar, the upside sweep (short) is taken; one signal per
symbol per session.
"""

from __future__ import annotations

from datetime import time

import pandas as pd

from trademind.services.feature_engine.context import clean
from trademind.services.strategy_engine.base import (
    Strategy,
    StrategyParams,
    buffered_stop,
    within_risk,
)
from trademind.services.strategy_engine.registry import register
from trademind.services.strategy_engine.view import BarView
from trademind.shared.enums import Side
from trademind.shared.models import Signal


class SweepReversalParams(StrategyParams):
    window_start: time = time(9, 30)
    window_end: time = time(14, 30)
    reclaim_minutes: int = 15
    max_sweep_pct: float = 0.5
    min_risk_pct: float = 0.15
    max_risk_pct: float = 1.0
    target_r: float = 2.0
    stop_buffer_atr: float = 0.0


@register
class SweepReversal(Strategy):
    id = "sweep_reversal"
    version = "1"
    scope = "all"
    Params = SweepReversalParams

    def on_bar(self, view: BarView) -> list[Signal]:
        if self.emitted(view.symbol):
            return []
        for side in (Side.SHORT, Side.LONG):
            sig = self._check(view, side)
            if sig is not None:
                return [sig]
        return []

    def _check(self, view: BarView, side: Side) -> Signal | None:
        p: SweepReversalParams = self.params  # type: ignore[assignment]
        short = side == Side.SHORT
        level = view.day.prev_day_high if short else view.day.prev_day_low
        if level is None:
            return None
        # opened on the near side of the level
        if (view.day.first_open > level) if short else (view.day.first_open < level):
            return None
        hist = view.history
        s_idx = next(
            (k for k, b in enumerate(hist) if (b["high"] > level if short else b["low"] < level)),
            None,
        )
        if s_idx is None:
            return None
        s_ts = hist[s_idx]["ts"]
        if not (p.window_start <= s_ts.time() < p.window_end):
            return None
        # 1. within the reclaim window: close_time(T) <= close_time(S) + reclaim
        if view.now > s_ts + pd.Timedelta(minutes=p.reclaim_minutes):
            return None
        close = float(view.bar["close"])
        # 2. back on the near side of the level
        if (close >= level) if short else (close <= level):
            return None
        span = hist[s_idx:]
        extreme = max(b["high"] for b in span) if short else min(b["low"] for b in span)
        sweep_pct = (extreme - level) / level * 100 if short else (level - extreme) / level * 100
        # 3. a poke, not a breakout
        if sweep_pct > p.max_sweep_pct:
            return None
        # 5. stop beyond the sweep extreme, risk bounds
        stop = buffered_stop(extreme, side, p.stop_buffer_atr, clean(view.bar.get("atr14")))
        if stop is None or not within_risk(close, stop, p.min_risk_pct, p.max_risk_pct):
            return None
        target = close - p.target_r * (stop - close) if short else close + p.target_r * (close - stop)
        extra = {
            "level": level,
            "level_kind": "pdh" if short else "pdl",
            "sweep_extreme": extreme,
            "sweep_pct": sweep_pct,
            "minutes_since_sweep": (view.now - s_ts) / pd.Timedelta(minutes=1),
        }
        reason = f"swept {'PDH' if short else 'PDL'} {level:.2f} to {extreme:.2f} and reclaimed"
        return self.signal(view, side, stop, target, reason, extra)
