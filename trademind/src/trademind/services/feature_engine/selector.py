"""Stocks in play (STRATEGIES A.5)."""

from __future__ import annotations

import math


def select_in_play(or_rvol: dict[str, float | None], top_n: int, min_or_rvol: float) -> set[str]:
    ok = [
        (sym, v)
        for sym, v in or_rvol.items()
        if v is not None and not math.isnan(v) and v >= min_or_rvol
    ]
    ok.sort(key=lambda kv: (-kv[1], kv[0]))
    return {sym for sym, _ in ok[:top_n]}
