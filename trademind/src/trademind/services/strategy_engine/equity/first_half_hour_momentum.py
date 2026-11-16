"""STRATEGIES C.5 `first_half_hour_momentum` v1: the opening move predicts the last half hour.

Indices only. Enters near 15:00 and exits at the 15:20 square-off.
"""

from __future__ import annotations

from datetime import time

import pandas as pd

from trademind.services.strategy_engine.base import Strategy, StrategyParams
from trademind.services.strategy_engine.registry import register
from trademind.services.strategy_engine.view import BarView
from trademind.shared.enums import Side
from trademind.shared.models import Signal


class FirstHalfHourParams(StrategyParams):
    measure_time: time = time(9, 45)
    signal_time: time = time(15, 0)
    min_move_pct: float = 0.2
    stop_pct: float = 0.3


@register
class FirstHalfHourMomentum(Strategy):
    id = "first_half_hour_momentum"
    version = "1"
    scope = "index"
    allow_late_entry = True
    Params = FirstHalfHourParams

    def on_bar(self, view: BarView) -> list[Signal]:
        p: FirstHalfHourParams = self.params  # type: ignore[assignment]
        if self.emitted(view.symbol) or view.day.prev_close is None:
            return []
        span = pd.Timedelta(minutes=view.minutes)

        def closes_by(b: dict, t: time) -> bool:
            return (b["ts"] + span).time() >= t

        hist = view.history
        # 2. this must be the first bar to close at or after the signal time
        if not closes_by(hist[-1], p.signal_time) or any(closes_by(b, p.signal_time) for b in hist[:-1]):
            return []
        # 1. the first bar to close at or after the measure time
        measure = next((b for b in hist if closes_by(b, p.measure_time)), None)
        if measure is None:
            return []
        r_open = (measure["close"] / view.day.prev_close - 1) * 100
        if abs(r_open) < p.min_move_pct:
            return []
        close = float(view.bar["close"])
        side = Side.LONG if r_open > 0 else Side.SHORT
        stop = close * (1 - p.stop_pct / 100) if side == Side.LONG else close * (1 + p.stop_pct / 100)
        reason = f"opening move {r_open:+.2f}%: follow into the close"
        return [self.signal(view, side, stop, None, reason, {"r_open": r_open})]
