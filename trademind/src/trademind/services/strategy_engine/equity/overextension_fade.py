"""STRATEGIES C.3 `overextension_fade` v1: fade stretched moves back to VWAP."""

from __future__ import annotations

import math
from datetime import time

from trademind.services.feature_engine.context import clean
from trademind.services.strategy_engine.base import Strategy, StrategyParams, within_risk
from trademind.services.strategy_engine.registry import register
from trademind.services.strategy_engine.view import BarView
from trademind.shared.enums import Side
from trademind.shared.models import Signal


class OverextensionFadeParams(StrategyParams):
    window_start: time = time(10, 0)
    window_end: time = time(14, 30)
    z_entry: float = 3.0
    z_lookback_bars: int = 3
    min_risk_pct: float = 0.15
    max_risk_pct: float = 1.0
    min_reward_risk: float = 1.0


def zscore(bar: dict) -> float | None:
    c, v, a = clean(bar.get("close")), clean(bar.get("vwap")), clean(bar.get("atr14"))
    if c is None or v is None or a is None or a <= 0:
        return None
    return (c - v) / a


@register
class OverextensionFade(Strategy):
    id = "overextension_fade"
    version = "1"
    scope = "all"
    Params = OverextensionFadeParams

    def on_bar(self, view: BarView) -> list[Signal]:
        p: OverextensionFadeParams = self.params  # type: ignore[assignment]
        if self.emitted(view.symbol):
            return []
        # 1. time window
        if not (p.window_start <= view.now.time() < p.window_end):
            return []
        prev = view.prev
        bar = view.bar
        if prev is None:
            return []
        zs = [z for z in (zscore(b) for b in view.history[-p.z_lookback_bars:]) if z is not None]
        z_now = zscore(bar)
        close, vwap = clean(bar.get("close")), clean(bar.get("vwap"))
        if not zs or close is None or vwap is None:
            return []
        if max(zs) >= p.z_entry:
            side, z_ext = Side.SHORT, max(zs)
        elif min(zs) <= -p.z_entry:
            side, z_ext = Side.LONG, min(zs)
        else:
            return []
        short = side == Side.SHORT
        # 3. reversal trigger, 4. still on the stretched side of VWAP
        if short and not (close < prev["low"] and close > vwap):
            return []
        if not short and not (close > prev["high"] and close < vwap):
            return []
        # 6. stop at the day's extreme so far, risk bounds
        stop = clean(bar.get("day_high") if short else bar.get("day_low"))
        if stop is None or not within_risk(close, stop, p.min_risk_pct, p.max_risk_pct):
            return []
        # 7. target VWAP with enough reward
        target = vwap
        reward_risk = (close - target) / (stop - close) if short else (target - close) / (close - stop)
        if not math.isfinite(reward_risk) or reward_risk < p.min_reward_risk:
            return []
        extra = {"z": z_now, "z_extreme": z_ext, "reward_risk": reward_risk}
        reason = f"stretched {z_ext:+.1f} ATR from VWAP and reversing"
        return [self.signal(view, side, stop, target, reason, extra)]
