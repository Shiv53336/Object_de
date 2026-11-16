"""Paper broker: simulated fills on base bars (PLAN 5.2, 5.3).

No real orders exist anywhere in this module. Each strategy instance has its own book,
keyed by (instance_id, symbol).

Order of work on each base bar of a symbol:
  1. exits at the open for open positions (gap through stop or target, time exit, square-off)
  2. pending entries fill at the open, or are cancelled
  3. intrabar stop/target for open positions, including ones filled on this bar
At-open exit precedence: STOP, TARGET, TIME, SQUAREOFF (all fill at the same open price).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import NamedTuple

import pandas as pd

from trademind.services.paper_broker.costs import compute_costs, slippage_fraction
from trademind.shared.config import CostsConfig, SessionConfig
from trademind.shared.enums import ExitReason, RejectReason, Side
from trademind.shared.models import Order, Trade


class Bar(NamedTuple):
    ts: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    g: int = -1  # index on the session base grid, when known


@dataclass(slots=True)
class EntryFilled:
    order: Order
    price: float
    ts: pd.Timestamp


@dataclass(slots=True)
class EntryCancelled:
    order: Order
    reason: RejectReason


@dataclass(slots=True)
class TradeClosed:
    trade: Trade
    exit_g: int


BrokerEvent = EntryFilled | EntryCancelled | TradeClosed


@dataclass(slots=True)
class Position:
    order: Order
    entry_ts: pd.Timestamp
    entry_price: float
    max_high: float
    min_low: float

    @property
    def side(self) -> Side:
        return self.order.signal.side


class PaperBroker:
    def __init__(self, costs: CostsConfig, session: SessionConfig, run_id: str = "") -> None:
        self.costs = costs
        self.session = session
        self.run_id = run_id
        self.pending: dict[tuple[str, str], Order] = {}
        self.positions: dict[tuple[str, str], Position] = {}
        self._active: dict[str, int] = {}
        self._trade_seq = 0

    # ---- bookkeeping -------------------------------------------------------------------
    def _touch(self, symbol: str, delta: int) -> None:
        n = self._active.get(symbol, 0) + delta
        if n:
            self._active[symbol] = n
        else:
            self._active.pop(symbol, None)

    def active_symbols(self) -> list[str]:
        return sorted(self._active)

    def open_count(self, instance_id: str) -> int:
        return sum(1 for (iid, _) in self.positions if iid == instance_id)

    def pending_count(self, instance_id: str) -> int:
        return sum(1 for (iid, _) in self.pending if iid == instance_id)

    def has_position_or_pending(self, instance_id: str, symbol: str) -> bool:
        key = (instance_id, symbol)
        return key in self.positions or key in self.pending

    def queue_entry(self, order: Order) -> None:
        key = (order.signal.instance_id, order.signal.symbol)
        if key in self.pending or key in self.positions:
            raise ValueError(f"{key} already has a pending order or position")
        self.pending[key] = order
        self._touch(order.signal.symbol, +1)

    # ---- fills -------------------------------------------------------------------------
    def _slip(self, order: Order) -> float:
        return slippage_fraction(order.instrument.trade_segment, self.costs)

    def _exit_fill(self, pos: Position, price: float) -> float:
        slip = self._slip(pos.order)
        return price * (1 - slip) if pos.side == Side.LONG else price * (1 + slip)

    def _close(self, key: tuple[str, str], pos: Position, bar: Bar, raw_price: float,
               reason: ExitReason) -> TradeClosed:
        sig, qty = pos.order.signal, pos.order.qty
        exit_price = self._exit_fill(pos, raw_price)
        if pos.side == Side.LONG:
            buy_v, sell_v = pos.entry_price * qty, exit_price * qty
            gross = (exit_price - pos.entry_price) * qty
            mfe = max(0.0, pos.max_high - pos.entry_price)
            mae = max(0.0, pos.entry_price - pos.min_low)
        else:
            buy_v, sell_v = exit_price * qty, pos.entry_price * qty
            gross = (pos.entry_price - exit_price) * qty
            mfe = max(0.0, pos.entry_price - pos.min_low)
            mae = max(0.0, pos.max_high - pos.entry_price)
        costs = compute_costs(pos.order.instrument.trade_segment, buy_v, sell_v, self.costs).total
        rpu = abs(pos.entry_price - sig.stop)
        net = gross - costs
        self._trade_seq += 1
        trade = Trade(
            trade_id=f"{self.run_id[:8]}-t{self._trade_seq:06d}",
            run_id=self.run_id,
            signal_id=pos.order.signal_id,
            strategy_id=sig.strategy_id,
            strategy_version=sig.strategy_version,
            timeframe=sig.timeframe,
            instance_id=sig.instance_id,
            symbol=sig.symbol,
            side=sig.side,
            qty=qty,
            signal_ts=sig.ts,
            entry_ts=pos.entry_ts,
            entry_price=pos.entry_price,
            exit_ts=bar.ts,
            exit_price=exit_price,
            exit_reason=reason,
            stop=sig.stop,
            target=sig.target,
            risk_per_unit=rpu,
            gross_pnl=gross,
            costs=costs,
            net_pnl=net,
            r_multiple=net / (qty * rpu),
            mfe_r=mfe / rpu,
            mae_r=mae / rpu,
            features=dict(sig.features),
        )
        del self.positions[key]
        self._touch(sig.symbol, -1)
        return TradeClosed(trade, bar.g)

    def _exit_at_open_reason(self, pos: Position, bar: Bar, t: time) -> ExitReason | None:
        sig = pos.order.signal
        o = bar.open
        long = pos.side == Side.LONG
        if (long and o <= sig.stop) or (not long and o >= sig.stop):
            return ExitReason.STOP
        if sig.target is not None and ((long and o >= sig.target) or (not long and o <= sig.target)):
            return ExitReason.TARGET
        if sig.time_exit is not None and t >= sig.time_exit:
            return ExitReason.TIME
        if t >= self.session.squareoff_time:
            return ExitReason.SQUAREOFF
        return None

    def _entry_block(self, order: Order, bar: Bar, t: time) -> RejectReason | None:
        sig = order.signal
        o = bar.open
        long = sig.side == Side.LONG
        if t >= self.session.squareoff_time:
            return RejectReason.AFTER_LAST_ENTRY
        if t >= self.session.last_entry_time and not order.allow_late_entry:
            return RejectReason.AFTER_LAST_ENTRY
        if (long and o <= sig.stop) or (not long and o >= sig.stop):
            return RejectReason.ENTRY_THROUGH_STOP
        if sig.target is not None and ((long and o >= sig.target) or (not long and o <= sig.target)):
            return RejectReason.ENTRY_THROUGH_TARGET
        return None

    def on_bar(self, symbol: str, bar: Bar) -> list[BrokerEvent]:
        events: list[BrokerEvent] = []
        t = bar.ts.time()
        # 1. exits at the open
        for key in [k for k in self.positions if k[1] == symbol]:
            pos = self.positions[key]
            reason = self._exit_at_open_reason(pos, bar, t)
            if reason is not None:
                pos.max_high = max(pos.max_high, bar.open)
                pos.min_low = min(pos.min_low, bar.open)
                events.append(self._close(key, pos, bar, bar.open, reason))
        # 2. pending entries
        for key in [k for k in self.pending if k[1] == symbol]:
            order = self.pending.pop(key)
            block = self._entry_block(order, bar, t)
            if block is not None:
                self._touch(symbol, -1)
                events.append(EntryCancelled(order, block))
                continue
            slip = self._slip(order)
            price = bar.open * (1 + slip) if order.signal.side == Side.LONG else bar.open * (1 - slip)
            self.positions[key] = Position(order, bar.ts, price, bar.open, bar.open)
            events.append(EntryFilled(order, price, bar.ts))
        # 3. intrabar stop / target
        for key in [k for k in self.positions if k[1] == symbol]:
            pos = self.positions[key]
            sig = pos.order.signal
            pos.max_high = max(pos.max_high, bar.high)
            pos.min_low = min(pos.min_low, bar.low)
            if pos.side == Side.LONG:
                if bar.low <= sig.stop:
                    events.append(self._close(key, pos, bar, sig.stop, ExitReason.STOP))
                elif sig.target is not None and bar.high >= sig.target:
                    events.append(self._close(key, pos, bar, sig.target, ExitReason.TARGET))
            else:
                if bar.high >= sig.stop:
                    events.append(self._close(key, pos, bar, sig.stop, ExitReason.STOP))
                elif sig.target is not None and bar.low <= sig.target:
                    events.append(self._close(key, pos, bar, sig.target, ExitReason.TARGET))
        return events

    def end_of_day(self, symbol: str, last_bar: Bar | None) -> list[BrokerEvent]:
        """Cancel leftover entries and close leftover positions at the last bar's close."""
        events: list[BrokerEvent] = []
        for key in [k for k in self.pending if k[1] == symbol]:
            order = self.pending.pop(key)
            self._touch(symbol, -1)
            events.append(EntryCancelled(order, RejectReason.NO_NEXT_BAR))
        for key in [k for k in self.positions if k[1] == symbol]:
            if last_bar is None:
                raise RuntimeError(f"open position on {symbol} with no bar to close it")
            pos = self.positions[key]
            events.append(self._close(key, pos, last_bar, last_bar.close, ExitReason.SQUAREOFF))
        return events
