"""Zerodha charges model (PLAN 7). No rounding of components in v1."""

from __future__ import annotations

from trademind.shared.config import CostsConfig, SegmentCost
from trademind.shared.enums import Segment
from trademind.shared.models import CostBreakdown


def _brokerage(order_value: float, sc: SegmentCost) -> float:
    if sc.brokerage_flat is not None:
        return sc.brokerage_flat
    b = order_value * sc.brokerage_pct
    return min(b, sc.brokerage_cap) if sc.brokerage_cap is not None else b


def compute_costs(
    segment: Segment, buy_value: float, sell_value: float, costs: CostsConfig
) -> CostBreakdown:
    """Round trip of two orders: one buy of buy_value, one sell of sell_value."""
    sc = costs.segments[segment]
    brokerage = _brokerage(buy_value, sc) + _brokerage(sell_value, sc)
    stt = buy_value * sc.stt_buy + sell_value * sc.stt_sell
    txn = (buy_value + sell_value) * sc.txn
    sebi = (buy_value + sell_value) * sc.sebi_per_crore / 1e7
    stamp = buy_value * sc.stamp_buy
    gst = costs.gst * (brokerage + sebi + txn)
    total = brokerage + stt + txn + sebi + stamp + gst
    return CostBreakdown(brokerage, stt, txn, sebi, stamp, gst, total)


def slippage_fraction(segment: Segment, costs: CostsConfig) -> float:
    return costs.slippage_bps[segment] / 10_000.0
