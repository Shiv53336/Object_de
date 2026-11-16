"""Strategy interface (BLUEPRINT 5.8, PLAN 4.5). A strategy returns proposals, never orders."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from datetime import date, time
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, field_validator

from trademind.services.feature_engine.context import clean
from trademind.services.strategy_engine.view import BarView
from trademind.shared.clock import tf_minutes
from trademind.shared.enums import Side
from trademind.shared.models import Instrument, Signal


def _parse_time(value: Any) -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    raise ValueError(f"times must be strings like \"11:00\", got {value!r}")


class StrategyParams(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*", mode="before")
    @classmethod
    def _times(cls, v: Any, info: Any) -> Any:
        field = cls.model_fields.get(info.field_name)
        if field is not None and field.annotation is time:
            return _parse_time(v)
        return v


def risk_pct(close: float, stop: float) -> float:
    return abs(close - stop) / close * 100


def within_risk(close: float, stop: float, lo: float, hi: float) -> bool:
    r = risk_pct(close, stop)
    return math.isfinite(r) and lo <= r <= hi


def buffered_stop(level: float, side: Side, buffer_atr: float, atr: float | None) -> float | None:
    """STRATEGIES Part C: stop a fraction of ATR beyond the level. None if ATR is needed but missing."""
    if buffer_atr == 0:
        return level
    if atr is None or not math.isfinite(atr):
        return None
    return level - buffer_atr * atr if side == Side.LONG else level + buffer_atr * atr


def market_above_vwap(view: BarView) -> bool | None:
    m = view.market
    if m is None:
        return None
    c, v = clean(m.bar.get("close")), clean(m.bar.get("vwap"))
    if c is None or v is None:
        return None
    return c > v


def base_features(view: BarView) -> dict:
    b, d = view.bar, view.day
    return {
        "close": clean(b.get("close")),
        "vwap": clean(b.get("vwap")),
        "atr14": clean(b.get("atr14")),
        "tod_rvol": clean(b.get("tod_rvol")),
        "or_rvol": clean(d.or_rvol),
        "gap_pct": clean(d.gap_pct),
        "market_above_vwap": market_above_vwap(view),
        "trend_15m": b.get("trend_15m"),
        "trend_60m": b.get("trend_60m"),
        "daily_trend": d.daily_trend,
    }


class Strategy(ABC):
    id: ClassVar[str]
    version: ClassVar[str]
    scope: ClassVar[str]  # "index" | "stocks" | "all"
    allow_late_entry: ClassVar[bool] = False
    Params: ClassVar[type[StrategyParams]] = StrategyParams

    def __init__(self, timeframe: str, params: dict | None = None) -> None:
        self.timeframe = timeframe
        self.minutes = tf_minutes(timeframe)
        self.params = self.Params.model_validate(params or {})
        self._emitted: set[str] = set()

    @property
    def instance_id(self) -> str:
        return f"{self.id}@{self.timeframe}"

    def in_scope(self, instrument: Instrument) -> bool:
        if self.scope == "all":
            return True
        if self.scope == "index":
            return instrument.kind == "index"
        if self.scope == "stocks":
            return instrument.kind == "stock"
        raise ValueError(f"bad scope {self.scope!r}")

    def on_day_start(self, day: date) -> None:
        """Reset per-session state. Subclasses that keep more state must call super()."""
        self._emitted = set()

    def emitted(self, symbol: str) -> bool:
        return symbol in self._emitted

    def signal(
        self,
        view: BarView,
        side: Side,
        stop: float,
        target: float | None,
        reason: str,
        extra: dict | None = None,
        time_exit: time | None = None,
    ) -> Signal:
        close = float(view.bar["close"])
        features = base_features(view)
        features["risk_pct"] = risk_pct(close, stop)
        if extra:
            features.update({k: (clean(v) if isinstance(v, float) else v) for k, v in extra.items()})
        self._emitted.add(view.symbol)
        return Signal(
            strategy_id=self.id,
            strategy_version=self.version,
            timeframe=self.timeframe,
            symbol=view.symbol,
            ts=view.now,
            side=side,
            stop=float(stop),
            target=None if target is None else float(target),
            time_exit=time_exit,
            features=features,
            reason=reason,
        )

    @abstractmethod
    def on_bar(self, view: BarView) -> list[Signal]:
        """Called at the close of every completed bar of this instance's timeframe."""
