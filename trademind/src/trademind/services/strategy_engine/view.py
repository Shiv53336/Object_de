"""What a strategy may see at a timeframe bar's close (PLAN 5.4).

DayFrames holds one symbol's data for one session. BarView exposes only completed bars up to
the current one, and base bars that opened before the current bar's close.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import numpy as np
import pandas as pd

from trademind.services.feature_engine.context import DayContext
from trademind.shared.clock import at
from trademind.shared.config import SessionConfig
from trademind.shared.models import Instrument


@dataclass(frozen=True, slots=True)
class OpeningRange:
    high: float
    low: float
    open: float
    close: float
    volume: int
    end: pd.Timestamp  # session_open + minutes


@dataclass
class DayFrames:
    symbol: str
    instrument: Instrument
    ctx: DayContext
    session: SessionConfig
    base: pd.DataFrame  # today's base bars with base features, index 0..n-1
    tf: dict[int, pd.DataFrame]  # minutes -> today's completed bars with features
    records: dict[int, list[dict]] = field(default_factory=dict)
    _or_cache: dict[int, OpeningRange | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for m, df in self.tf.items():
            self.records[m] = df.to_dict("records")
        self._base_ns = pd.DatetimeIndex(self.base["ts"]).as_unit("ns").asi8

    @cached_property
    def open_ts(self) -> pd.Timestamp:
        return at(self.ctx.day, self.session.open)

    def base_count_before(self, ts: pd.Timestamp) -> int:
        """Number of base bars that opened strictly before ts."""
        return int(np.searchsorted(self._base_ns, ts.value, side="left"))

    def opening_range(self, minutes: int) -> OpeningRange | None:
        if minutes not in self._or_cache:
            end = self.open_ts + pd.Timedelta(minutes=minutes)
            sub = self.base.iloc[: self.base_count_before(end)]
            if sub.empty:
                self._or_cache[minutes] = None
            else:
                self._or_cache[minutes] = OpeningRange(
                    high=float(sub["high"].max()),
                    low=float(sub["low"].min()),
                    open=float(sub["open"].iloc[0]),
                    close=float(sub["close"].iloc[-1]),
                    volume=int(sub["volume"].sum()),
                    end=end,
                )
        return self._or_cache[minutes]


class BarView:
    """A strategy's window onto one symbol at the close of one timeframe bar."""

    __slots__ = ("frames", "minutes", "timeframe", "row", "market")

    def __init__(
        self, frames: DayFrames, minutes: int, timeframe: str, row: int, market: BarView | None
    ) -> None:
        self.frames = frames
        self.minutes = minutes
        self.timeframe = timeframe
        self.row = row
        self.market = market

    @property
    def symbol(self) -> str:
        return self.frames.symbol

    @property
    def instrument(self) -> Instrument:
        return self.frames.instrument

    @property
    def day(self) -> DayContext:
        return self.frames.ctx

    @property
    def bar(self) -> dict:
        return self.frames.records[self.minutes][self.row]

    @property
    def prev(self) -> dict | None:
        return self.frames.records[self.minutes][self.row - 1] if self.row > 0 else None

    @property
    def history(self) -> list[dict]:
        """Today's completed bars of this timeframe up to and including the current one."""
        return self.frames.records[self.minutes][: self.row + 1]

    @property
    def bars(self) -> pd.DataFrame:
        return self.frames.tf[self.minutes].iloc[: self.row + 1]

    @property
    def now(self) -> pd.Timestamp:
        return self.bar["ts"]

    @property
    def close_time(self) -> pd.Timestamp:
        return self.now + pd.Timedelta(minutes=self.minutes)

    @property
    def i(self) -> int:
        """Index of the current bar on today's timeframe grid (correct even with missing bars)."""
        return int((self.now - self.frames.open_ts) / pd.Timedelta(minutes=self.minutes))

    @property
    def base(self) -> pd.DataFrame:
        return self.frames.base.iloc[: self.frames.base_count_before(self.close_time)]

    def opening_range(self, minutes: int) -> OpeningRange | None:
        """STRATEGIES A.3: None until the clock reaches the end of the range."""
        if self.close_time < self.frames.open_ts + pd.Timedelta(minutes=minutes):
            return None
        return self.frames.opening_range(minutes)
