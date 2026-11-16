from __future__ import annotations

from datetime import time

import pytest

from trademind.services.paper_broker.broker import (
    EntryCancelled,
    EntryFilled,
    PaperBroker,
    TradeClosed,
)
from trademind.services.paper_broker.costs import compute_costs
from trademind.shared.config import AppConfig
from trademind.shared.enums import ExitReason, RejectReason, Segment, Side

from .helpers import bar, order, signal

SLIP = 0.0003


@pytest.fixture
def broker(cfg: AppConfig) -> PaperBroker:
    return PaperBroker(cfg.costs, cfg.settings.session, run_id="testrun0")


def _closed(events) -> list:
    return [e.trade for e in events if isinstance(e, TradeClosed)]


def _filled(broker: PaperBroker, sig, entry_bar, **kw):
    broker.queue_entry(order(sig, **kw))
    return broker.on_bar("AAA", entry_bar)


def test_long_entry_at_next_open_with_slippage(broker: PaperBroker) -> None:
    ev = _filled(broker, signal(), bar("10:05", 100, 101, 99.5, 100.5))
    assert isinstance(ev[0], EntryFilled)
    assert ev[0].price == pytest.approx(100 * (1 + SLIP))
    assert broker.open_count("probe@5minute") == 1


def test_short_entry_slippage(broker: PaperBroker) -> None:
    ev = _filled(broker, signal(Side.SHORT, stop=105, target=90), bar("10:05", 100, 101, 99.5, 100.5))
    assert ev[0].price == pytest.approx(100 * (1 - SLIP))


@pytest.mark.parametrize(
    "sig,b,late,reason",
    [
        (signal(), bar("14:45", 100, 101, 99, 100), False, RejectReason.AFTER_LAST_ENTRY),
        (signal(), bar("15:20", 100, 101, 99, 100), True, RejectReason.AFTER_LAST_ENTRY),
        (signal(stop=95), bar("10:05", 94, 96, 93, 95), False, RejectReason.ENTRY_THROUGH_STOP),
        (signal(target=110), bar("10:05", 111, 112, 110, 111), False, RejectReason.ENTRY_THROUGH_TARGET),
        (signal(Side.SHORT, stop=105, target=90), bar("10:05", 106, 107, 105, 106), False,
         RejectReason.ENTRY_THROUGH_STOP),
    ],
)
def test_entry_cancellations(broker: PaperBroker, sig, b, late, reason) -> None:
    ev = _filled(broker, sig, b, late=late)
    assert isinstance(ev[0], EntryCancelled) and ev[0].reason == reason
    assert broker.active_symbols() == []


def test_late_entry_allowed_before_squareoff(broker: PaperBroker) -> None:
    ev = _filled(broker, signal(), bar("15:00", 100, 101, 99, 100), late=True)
    assert isinstance(ev[0], EntryFilled)


def test_intrabar_stop(broker: PaperBroker) -> None:
    _filled(broker, signal(), bar("10:05", 100, 101, 99, 100.5))
    (t,) = _closed(broker.on_bar("AAA", bar("10:06", 100, 100.5, 94, 95)))
    assert t.exit_reason == ExitReason.STOP
    assert t.exit_price == pytest.approx(95 * (1 - SLIP))


def test_intrabar_target(broker: PaperBroker) -> None:
    _filled(broker, signal(), bar("10:05", 100, 101, 99, 100.5))
    (t,) = _closed(broker.on_bar("AAA", bar("10:06", 100, 111, 99, 110.5)))
    assert t.exit_reason == ExitReason.TARGET
    assert t.exit_price == pytest.approx(110 * (1 - SLIP))


def test_stop_and_target_in_same_bar_is_stop(broker: PaperBroker) -> None:
    _filled(broker, signal(), bar("10:05", 100, 101, 99, 100.5))
    (t,) = _closed(broker.on_bar("AAA", bar("10:06", 100, 111, 94, 100)))
    assert t.exit_reason == ExitReason.STOP


def test_gap_through_stop_exits_at_open(broker: PaperBroker) -> None:
    _filled(broker, signal(), bar("10:05", 100, 101, 99, 100.5))
    (t,) = _closed(broker.on_bar("AAA", bar("10:06", 93, 94, 92, 93)))
    assert t.exit_reason == ExitReason.STOP
    assert t.exit_price == pytest.approx(93 * (1 - SLIP))


def test_gap_through_target_exits_at_open(broker: PaperBroker) -> None:
    _filled(broker, signal(), bar("10:05", 100, 101, 99, 100.5))
    (t,) = _closed(broker.on_bar("AAA", bar("10:06", 112, 113, 111, 112)))
    assert t.exit_reason == ExitReason.TARGET
    assert t.exit_price == pytest.approx(112 * (1 - SLIP))


def test_short_gap_through_stop(broker: PaperBroker) -> None:
    _filled(broker, signal(Side.SHORT, stop=105, target=90), bar("10:05", 100, 101, 99, 100))
    (t,) = _closed(broker.on_bar("AAA", bar("10:06", 107, 108, 106, 107)))
    assert t.exit_reason == ExitReason.STOP
    assert t.exit_price == pytest.approx(107 * (1 + SLIP))


def test_stop_hit_on_entry_bar(broker: PaperBroker) -> None:
    ev = _filled(broker, signal(), bar("10:05", 100, 101, 94, 96))
    assert isinstance(ev[0], EntryFilled)
    (t,) = _closed(ev)
    assert t.exit_reason == ExitReason.STOP and t.entry_ts == t.exit_ts


def test_time_exit(broker: PaperBroker) -> None:
    _filled(broker, signal(time_exit=time(10, 30)), bar("10:05", 100, 101, 99, 100.5))
    assert _closed(broker.on_bar("AAA", bar("10:29", 100, 101, 99, 100))) == []
    (t,) = _closed(broker.on_bar("AAA", bar("10:30", 101, 102, 100, 101)))
    assert t.exit_reason == ExitReason.TIME and t.exit_price == pytest.approx(101 * (1 - SLIP))


def test_squareoff(broker: PaperBroker) -> None:
    _filled(broker, signal(), bar("10:05", 100, 101, 99, 100.5))
    (t,) = _closed(broker.on_bar("AAA", bar("15:20", 102, 103, 101, 102)))
    assert t.exit_reason == ExitReason.SQUAREOFF
    assert broker.active_symbols() == []


def test_end_of_day_closes_and_cancels(broker: PaperBroker) -> None:
    _filled(broker, signal(), bar("10:05", 100, 101, 99, 100.5))
    broker.queue_entry(order(signal(strategy_id="other")))
    ev = broker.end_of_day("AAA", bar("14:59", 101, 101, 100, 100.8))
    kinds = {type(e) for e in ev}
    assert kinds == {EntryCancelled, TradeClosed}
    cancelled = next(e for e in ev if isinstance(e, EntryCancelled))
    assert cancelled.reason == RejectReason.NO_NEXT_BAR
    (t,) = _closed(ev)
    assert t.exit_reason == ExitReason.SQUAREOFF and t.exit_price == pytest.approx(100.8 * (1 - SLIP))


def test_mfe_mae_ignore_range_of_exit_at_open_bar(broker: PaperBroker) -> None:
    _filled(broker, signal(target=None), bar("10:05", 100, 102, 99, 101))
    broker.on_bar("AAA", bar("10:06", 101, 104, 100, 103))
    (t,) = _closed(broker.on_bar("AAA", bar("15:20", 103.5, 120, 80, 110)))
    entry = 100 * (1 + SLIP)
    rpu = entry - 95
    assert t.mfe_r == pytest.approx((104 - entry) / rpu)
    assert t.mae_r == pytest.approx((entry - 99) / rpu)


def test_round_trip_pnl_costs_and_r(cfg: AppConfig, broker: PaperBroker) -> None:
    _filled(broker, signal(), bar("10:05", 100, 101, 99, 100.5))
    (t,) = _closed(broker.on_bar("AAA", bar("10:06", 100, 111, 99, 110.5)))
    entry, exit_ = 100 * (1 + SLIP), 110 * (1 - SLIP)
    costs = compute_costs(Segment.EQ_INTRADAY, entry * 10, exit_ * 10, cfg.costs).total
    assert t.gross_pnl == pytest.approx((exit_ - entry) * 10)
    assert t.costs == pytest.approx(costs)
    assert t.net_pnl == pytest.approx(t.gross_pnl - costs)
    assert t.r_multiple == pytest.approx(t.net_pnl / (10 * (entry - 95)))


def test_instances_are_independent(broker: PaperBroker) -> None:
    broker.queue_entry(order(signal()))
    broker.queue_entry(order(signal(strategy_id="other")))
    with pytest.raises(ValueError):
        broker.queue_entry(order(signal()))
    broker.on_bar("AAA", bar("10:05", 100, 101, 99, 100.5))
    assert broker.open_count("probe@5minute") == 1
    assert broker.open_count("other@5minute") == 1
