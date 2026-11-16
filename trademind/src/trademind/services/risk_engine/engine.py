"""Independent, fail-closed risk engine (PLAN 6, BLUEPRINT 5.11).

Strategies propose; this engine decides. Missing or invalid inputs are rejected, never sized.
State is per strategy instance and resets every session.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from trademind.shared.config import RiskConfig
from trademind.shared.enums import RejectReason, Side
from trademind.shared.models import Instrument, Signal, Trade


@dataclass(frozen=True, slots=True)
class Decision:
    approved: bool
    qty: int
    reason: RejectReason | None


@dataclass(slots=True)
class _InstanceDay:
    approvals: int = 0
    consecutive_losses: int = 0
    realised_r: float = 0.0
    trade_ids: set[str] = field(default_factory=set)


def _finite(*xs: float | None) -> bool:
    return all(x is not None and math.isfinite(x) for x in xs)


class RiskEngine:
    def __init__(self, cfg: RiskConfig) -> None:
        self.cfg = cfg
        self.day: date | None = None
        self._state: dict[str, _InstanceDay] = {}

    def start_day(self, day: date) -> None:
        self.day = day
        self._state = {}

    def _st(self, instance_id: str) -> _InstanceDay:
        return self._state.setdefault(instance_id, _InstanceDay())

    def size(self, ref_price: float, stop: float, instrument: Instrument) -> int:
        rpu = abs(ref_price - stop)
        lot = instrument.lot_size
        risk_inr, max_notional = self.cfg.limits(instrument.trade_segment)
        qty = math.floor(risk_inr / rpu)
        qty = (qty // lot) * lot
        cap = (math.floor(max_notional / ref_price) // lot) * lot
        return min(qty, cap)

    def evaluate(
        self,
        signal: Signal,
        ref_price: float,
        instrument: Instrument,
        *,
        open_positions: int,
        pending: int,
        has_position_or_pending: bool,
    ) -> Decision:
        def reject(r: RejectReason) -> Decision:
            return Decision(False, 0, r)

        st = self._st(signal.instance_id)
        if self.cfg.kill_switch:
            return reject(RejectReason.KILL_SWITCH)
        if not _finite(ref_price, signal.stop) or ref_price <= 0 or signal.stop <= 0:
            return reject(RejectReason.INVALID_INPUT)
        if signal.target is not None and not _finite(signal.target):
            return reject(RejectReason.INVALID_INPUT)
        long = signal.side == Side.LONG
        if (long and signal.stop > ref_price) or (not long and signal.stop < ref_price):
            return reject(RejectReason.INVALID_INPUT)
        if signal.target is not None and (
            (long and signal.target <= ref_price) or (not long and signal.target >= ref_price)
        ):
            return reject(RejectReason.INVALID_INPUT)
        if abs(ref_price - signal.stop) <= 0:
            return reject(RejectReason.ZERO_RISK)
        if has_position_or_pending:
            return reject(RejectReason.POSITION_EXISTS)
        if open_positions + pending >= self.cfg.max_open_positions:
            return reject(RejectReason.MAX_OPEN_POSITIONS)
        if st.approvals >= self.cfg.max_trades_per_day:
            return reject(RejectReason.MAX_TRADES_PER_DAY)
        if st.consecutive_losses >= self.cfg.max_consecutive_losses:
            return reject(RejectReason.CONSECUTIVE_LOSSES)
        if st.realised_r <= self.cfg.daily_loss_limit_r:
            return reject(RejectReason.DAILY_LOSS_LIMIT)
        qty = self.size(ref_price, signal.stop, instrument)
        if qty < instrument.lot_size:
            return reject(RejectReason.QTY_TOO_SMALL)
        st.approvals += 1
        return Decision(True, qty, None)

    def on_trade_closed(self, trade: Trade) -> None:
        st = self._st(trade.instance_id)
        if trade.trade_id in st.trade_ids:
            return
        st.trade_ids.add(trade.trade_id)
        st.realised_r += trade.r_multiple
        st.consecutive_losses = st.consecutive_losses + 1 if trade.net_pnl < 0 else 0
