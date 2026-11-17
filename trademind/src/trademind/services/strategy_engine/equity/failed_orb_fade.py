"""STRATEGIES C.2 `failed_orb_fade` v1: trade the opening-range breakout that fails.

If both sides qualify on the same bar, the short (failed upside breakout) is taken.
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
from trademind.services.strategy_engine.view import BarView, OpeningRange
from trademind.shared.enums import Side
from trademind.shared.models import Signal


class FailedOrbFadeParams(StrategyParams):
    or_minutes: int = 15
    bo_end: time = time(11, 0)
    fail_window_minutes: int = 30
    min_risk_pct: float = 0.15
    max_risk_pct: float = 1.0
    min_reward_risk: float = 1.0
    stop_buffer_atr: float = 0.0


@register
class FailedOrbFade(Strategy):
    id = "failed_orb_fade"
    version = "1"
    scope = "all"
    Params = FailedOrbFadeParams

    def on_bar(self, view: BarView) -> list[Signal]:
        if self.emitted(view.symbol):
            return []
        p: FailedOrbFadeParams = self.params  # type: ignore[assignment]
        orng = view.opening_range(p.or_minutes)
        if orng is None:
            return []
        for side in (Side.SHORT, Side.LONG):
            sig = self._check(view, orng, side, p)
            if sig is not None:
                return [sig]
        return []

    def _check(self, view: BarView, orng: OpeningRange, side: Side, p: FailedOrbFadeParams) -> Signal | None:
        short = side == Side.SHORT  # short fades an upside breakout
        hist = view.history
        b_idx = next(
            (
                k
                for k, b in enumerate(hist)
                if b["ts"] >= orng.end and (b["close"] > orng.high if short else b["close"] < orng.low)
            ),
            None,
        )
        if b_idx is None:
            return None
        b_ts = hist[b_idx]["ts"]
        if b_ts.time() >= p.bo_end:
            return None  # the first breakout came too late: no event today
        # 1. within the failure window, after the breakout bar
        if not (view.now > b_ts and view.now <= b_ts + pd.Timedelta(minutes=p.fail_window_minutes)):
            return None
        close = float(view.bar["close"])
        # 2. closed back inside the range
        if (close >= orng.high) if short else (close <= orng.low):
            return None
        span = hist[b_idx:]
        extreme = max(b["high"] for b in span) if short else min(b["low"] for b in span)
        # 4. stop beyond the breakout extreme, risk bounds
        stop = buffered_stop(extreme, Side.SHORT if short else Side.LONG, p.stop_buffer_atr,
                             clean(view.bar.get("atr14")))
        if stop is None or not within_risk(close, stop, p.min_risk_pct, p.max_risk_pct):
            return None
        # 5. target at the other side of the range, enough reward for the risk
        target = orng.low if short else orng.high
        reward_risk = (close - target) / (stop - close) if short else (target - close) / (close - stop)
        if reward_risk < p.min_reward_risk:
            return None
        extra = {
            "or_high": orng.high,
            "or_low": orng.low,
            "minutes_since_breakout": (view.now - b_ts) / pd.Timedelta(minutes=1),
            "bo_extreme": extreme,
            "reward_risk": reward_risk,
        }
        reason = f"failed {'upside' if short else 'downside'} ORB, back inside the range"
        return self.signal(view, side, stop, target, reason, extra)
