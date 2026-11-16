"""Shared domain objects (PLAN 4.3 and 4.5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

import pandas as pd

from trademind.shared.enums import ExitReason, Segment, Side


@dataclass(frozen=True, slots=True)
class Instrument:
    symbol: str
    exchange: str
    kind: str  # "stock" | "index"
    trade_segment: Segment
    lot_size: int
    tick_size: float
    has_volume: bool


@dataclass(frozen=True, slots=True)
class Signal:
    strategy_id: str
    strategy_version: str
    timeframe: str
    symbol: str
    ts: pd.Timestamp  # open time of the timeframe bar whose close produced the signal
    side: Side
    stop: float
    target: float | None
    time_exit: time | None
    features: dict = field(default_factory=dict)
    reason: str = ""

    @property
    def instance_id(self) -> str:
        return f"{self.strategy_id}@{self.timeframe}"


@dataclass(frozen=True, slots=True)
class Order:
    signal_id: str
    signal: Signal
    qty: int
    instrument: Instrument
    allow_late_entry: bool = False


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    brokerage: float
    stt: float
    txn: float
    sebi: float
    stamp: float
    gst: float
    total: float


@dataclass(slots=True)
class Trade:
    trade_id: str
    run_id: str
    signal_id: str
    strategy_id: str
    strategy_version: str
    timeframe: str
    instance_id: str
    symbol: str
    side: Side
    qty: int
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    entry_price: float
    exit_ts: pd.Timestamp
    exit_price: float
    exit_reason: ExitReason
    stop: float
    target: float | None
    risk_per_unit: float
    gross_pnl: float
    costs: float
    net_pnl: float
    r_multiple: float
    mfe_r: float
    mae_r: float
    post_exit_mfe_r: float | None = None
    target_hit_after_stop: bool | None = None
    features: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
