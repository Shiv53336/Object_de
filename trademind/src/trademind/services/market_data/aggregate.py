"""Ticks to base bars (T08).

A bar [T, T + base) completes when a later-minute tick arrives for that symbol, or when
`flush(now)` is called with now >= T + base. Bar volume is the change in the exchange's
cumulative day volume between this bar's last tick and the previous bar's last tick.
A minute with no ticks produces no bar, matching Kite's own candles (PLAN 4.1).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from trademind.shared.clock import IST
from trademind.shared.config import SessionConfig


@dataclass(slots=True)
class _Building:
    ts: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    last_tick: pd.Timestamp
    cum: int | None


class BarAggregator:
    def __init__(self, session: SessionConfig) -> None:
        self.session = session
        self.base = pd.Timedelta(minutes=session.base_minutes)
        self._cur: dict[str, _Building] = {}
        self._prev_cum: dict[str, int] = {}
        self._last_done: dict[str, pd.Timestamp] = {}
        self.late_ticks = 0

    def seed(self, symbol: str, cumulative_volume: int, last_bar_ts: pd.Timestamp | None = None) -> None:
        """After a backfill: cumulative volume so far, and the last bar already known."""
        self._prev_cum[symbol] = int(cumulative_volume)
        if last_bar_ts is not None:
            self._last_done[symbol] = last_bar_ts

    def _bucket(self, ts: pd.Timestamp) -> pd.Timestamp | None:
        o = self.session.open
        day_open = ts.normalize() + pd.Timedelta(hours=o.hour, minutes=o.minute)
        offset = ts - day_open
        if offset < pd.Timedelta(0) or offset >= pd.Timedelta(minutes=self.session.length_minutes):
            return None
        return day_open + (offset // self.base) * self.base

    def _complete(self, symbol: str) -> dict:
        b = self._cur.pop(symbol)
        if b.cum is None:
            volume = 0
        else:
            volume = max(0, b.cum - self._prev_cum.get(symbol, 0))
            self._prev_cum[symbol] = b.cum
        self._last_done[symbol] = b.ts
        return {
            "symbol": symbol,
            "ts": b.ts,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": volume,
        }

    def on_tick(
        self, symbol: str, ts: pd.Timestamp, price: float, cumulative_volume: int | None = None
    ) -> list[dict]:
        ts = ts.tz_localize(IST) if ts.tzinfo is None else ts.tz_convert(IST)
        bucket = self._bucket(ts)
        if bucket is None:
            return []
        done = self._last_done.get(symbol)
        if done is not None and bucket <= done:
            self.late_ticks += 1
            return []
        out: list[dict] = []
        cur = self._cur.get(symbol)
        if cur is not None and bucket < cur.ts:
            self.late_ticks += 1
            return []
        if cur is not None and bucket > cur.ts:
            out.append(self._complete(symbol))
            cur = None
        if cur is None:
            cur = _Building(bucket, price, price, price, price, ts, None)
            self._cur[symbol] = cur
        else:
            cur.high = max(cur.high, price)
            cur.low = min(cur.low, price)
            if ts >= cur.last_tick:
                cur.close = price
                cur.last_tick = ts
        if cumulative_volume is not None:
            cur.cum = max(cur.cum or 0, int(cumulative_volume))
        return out

    def flush(self, now: pd.Timestamp) -> list[dict]:
        now = now.tz_localize(IST) if now.tzinfo is None else now.tz_convert(IST)
        return [self._complete(sym) for sym in sorted(self._cur) if self._cur[sym].ts + self.base <= now]
