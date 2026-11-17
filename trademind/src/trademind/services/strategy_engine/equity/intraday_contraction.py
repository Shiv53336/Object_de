"""STRATEGIES C.4 `intraday_contraction` v1: tightening ranges on fading volume, then a breakout.

The VCP idea on intraday bars. Long only, stocks in play only.
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


class IntradayContractionParams(StrategyParams):
    window_start: time = time(10, 15)
    window_end: time = time(14, 30)
    block_bars: int = 4
    n_blocks: int = 3
    max_final_to_first_range: float = 0.5
    max_base_rvol: float = 0.8
    min_trigger_rvol: float = 1.5
    min_risk_pct: float = 0.15
    max_risk_pct: float = 1.0
    target_r: float = 2.0
    stop_buffer_atr: float = 0.0


@register
class IntradayContraction(Strategy):
    id = "intraday_contraction"
    version = "1"
    scope = "stocks"
    Params = IntradayContractionParams

    def on_bar(self, view: BarView) -> list[Signal]:
        p: IntradayContractionParams = self.params  # type: ignore[assignment]
        if self.emitted(view.symbol):
            return []
        # 1. window and in play
        if not (p.window_start <= view.now.time() < p.window_end) or not view.day.in_play:
            return []
        n_base = p.block_bars * p.n_blocks
        i = view.i
        if i < n_base:
            return []
        step = pd.Timedelta(minutes=view.minutes)
        by_ts = {b["ts"]: b for b in view.history}
        base = [by_ts.get(view.now - step * (n_base - k)) for k in range(n_base)]
        if any(b is None for b in base):
            return []  # the consolidation must be complete
        blocks = [base[k * p.block_bars:(k + 1) * p.block_bars] for k in range(p.n_blocks)]
        ranges = [max(b["high"] for b in blk) - min(b["low"] for b in blk) for blk in blocks]
        # 2. each block tighter than the one before, 3. last block at most a fraction of the first
        if any(later >= earlier for earlier, later in zip(ranges, ranges[1:], strict=False)):
            return []
        if ranges[-1] > p.max_final_to_first_range * ranges[0]:
            return []
        # 4. volume dried up in the last block
        rvols = [clean(b.get("tod_rvol")) for b in blocks[-1]]
        if any(r is None for r in rvols) or sum(rvols) / len(rvols) >= p.max_base_rvol:
            return []
        # 5. consolidation sat above VWAP
        last = base[-1]
        lv = clean(last.get("vwap"))
        if lv is None or last["close"] <= lv:
            return []
        # 6. breakout above the pivot, 7. on a volume surge
        bar = view.bar
        close = float(bar["close"])
        pivot = max(b["high"] for b in base)
        trigger_rvol = clean(bar.get("tod_rvol"))
        if close <= pivot or trigger_rvol is None or trigger_rvol < p.min_trigger_rvol:
            return []
        # 9. stop under the last block, risk bounds
        level = min(b["low"] for b in blocks[-1])
        stop = buffered_stop(level, Side.LONG, p.stop_buffer_atr, clean(bar.get("atr14")))
        if stop is None or not within_risk(close, stop, p.min_risk_pct, p.max_risk_pct):
            return []
        target = close + p.target_r * (close - stop)
        extra = {f"range_{k + 1}": r for k, r in enumerate(ranges)}
        extra |= {"base_rvol": sum(rvols) / len(rvols), "trigger_rvol": trigger_rvol, "pivot": pivot}
        return [self.signal(view, Side.LONG, stop, target, "contraction breakout", extra)]
