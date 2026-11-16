"""Market-session time helpers. All timestamps are tz-aware Asia/Kolkata; a bar's ts is its open."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

IST = ZoneInfo("Asia/Kolkata")


def tf_minutes(interval: str) -> int:
    """'1minute' -> 1, '15minute' -> 15. Raises for 'day' and anything else."""
    if not interval.endswith("minute"):
        raise ValueError(f"not an intraday interval: {interval!r}")
    n = interval.removesuffix("minute")
    if not n.isdigit() or int(n) <= 0:
        raise ValueError(f"bad interval: {interval!r}")
    return int(n)


def at(day: date, t: time) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(day, t), tz=IST)


def minutes_between(start: time, end: time) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def session_grid(day: date, open_t: time, close_t: time, minutes: int) -> pd.DatetimeIndex:
    """Bar open times from open to close (exclusive). 375 one-minute or 75 five-minute stamps."""
    n = minutes_between(open_t, close_t) // minutes
    return pd.date_range(at(day, open_t), periods=n, freq=f"{minutes}min")


def in_window(t: time, start: time, end: time) -> bool:
    """[start, end) on a time of day."""
    return start <= t < end


def add_minutes(t: time, minutes: int) -> time:
    total = t.hour * 60 + t.minute + minutes
    return time(total // 60, total % 60)


def file_symbol(symbol: str) -> str:
    return symbol.replace(" ", "_")
