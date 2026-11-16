"""STRATEGIES C.1 `orb_momentum` v1: opening range breakout with trend and volume filters.

Reference implementation: other strategies should follow this structure.
"""

from __future__ import annotations

from datetime import time

from trademind.services.feature_engine.context import clean
from trademind.services.strategy_engine.base import (
    Strategy,
    StrategyParams,
    buffered_stop,
    market_above_vwap,
    within_risk,
)
from trademind.services.strategy_engine.registry import register
from trademind.services.strategy_engine.view import BarView
from trademind.shared.enums import Side
from trademind.shared.models import Signal


class OrbMomentumParams(StrategyParams):
    or_minutes: int = 15
    entry_end: time = time(11, 0)
    min_or_rvol: float = 1.5
    min_risk_pct: float = 0.15
    max_risk_pct: float = 1.0
    target_r: float = 2.0
    require_market_agree: bool = True
    stop_buffer_atr: float = 0.0


@register
class OrbMomentum(Strategy):
    id = "orb_momentum"
    version = "1"
    scope = "all"
    Params = OrbMomentumParams

    def on_bar(self, view: BarView) -> list[Signal]:
        p: OrbMomentumParams = self.params  # type: ignore[assignment]
        if self.emitted(view.symbol):
            return []
        orng = view.opening_range(p.or_minutes)
        if orng is None:
            return []
        now = view.now
        # 1. window: T >= or_end and T < entry_end
        if now < orng.end or now.time() >= p.entry_end:
            return []
        bar = view.bar
        close = float(bar["close"])
        if close > orng.high:
            side = Side.LONG
        elif close < orng.low:
            side = Side.SHORT
        else:
            return []
        long = side == Side.LONG
        # 2. first close beyond the range since or_end
        for b in view.history[:-1]:
            if b["ts"] >= orng.end and (b["close"] > orng.high if long else b["close"] < orng.low):
                return []
        # 4. opening direction agrees
        if (orng.close > orng.open) != long or orng.close == orng.open:
            return []
        # 5. VWAP side
        vwap = clean(bar.get("vwap"))
        if vwap is None or (close <= vwap if long else close >= vwap):
            return []
        # 6. stocks must be in play with enough opening volume
        if view.instrument.kind == "stock":
            rv = view.day.or_rvol
            if not view.day.in_play or rv is None or rv < p.min_or_rvol:
                return []
        # 7. market agrees
        if p.require_market_agree and view.market is not None and view.market.symbol != view.symbol:
            mav = market_above_vwap(view)
            if mav is None or mav != long:
                return []
        # 8. stop and risk bounds
        level = orng.low if long else orng.high
        stop = buffered_stop(level, side, p.stop_buffer_atr, clean(bar.get("atr14")))
        if stop is None or not within_risk(close, stop, p.min_risk_pct, p.max_risk_pct):
            return []
        target = close + p.target_r * (close - stop) if long else close - p.target_r * (stop - close)
        extra = {
            "or_high": orng.high,
            "or_low": orng.low,
            "or_width_pct": (orng.high - orng.low) / ((orng.high + orng.low) / 2) * 100,
            "opening_dir": "up" if long else "down",
        }
        reason = f"ORB {'up' if long else 'down'} through {level:.2f}"
        return [self.signal(view, side, stop, target, reason, extra)]
