"""Derived bars from base bars (PLAN 4.1). Buckets are anchored at the session open; a bucket
that cannot reach full length before the close is dropped, so strategies never see it."""

from __future__ import annotations

import pandas as pd

from trademind.shared.config import SessionConfig

CARRY_LAST = ("vwap", "day_high", "day_low", "trend_15m", "trend_60m", "oi")


def bucket_open(ts: pd.Series, session: SessionConfig, minutes: int) -> tuple[pd.Series, pd.Series]:
    """Returns (bucket open time, bucket is complete) for each timestamp."""
    day_open = ts.dt.normalize() + pd.Timedelta(hours=session.open.hour, minutes=session.open.minute)
    offset = ((ts - day_open) // pd.Timedelta(minutes=1)).astype("int64")
    bucket = offset // minutes
    opens = day_open + pd.to_timedelta(bucket * minutes, unit="min")
    complete = (bucket + 1) * minutes <= session.length_minutes
    return opens, complete


def resample_bars(base: pd.DataFrame, minutes: int, session: SessionConfig) -> pd.DataFrame:
    if base.empty:
        return base.copy()
    if minutes == session.base_minutes:
        return base.reset_index(drop=True).copy()
    if minutes % session.base_minutes:
        raise ValueError("timeframe must be a multiple of the base interval")
    opens, complete = bucket_open(base["ts"], session, minutes)
    df = base.assign(_bucket=opens)[complete.to_numpy()]
    agg: dict[str, str] = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    for col in CARRY_LAST:
        if col in df.columns:
            agg[col] = "last"
    out = df.groupby("_bucket", sort=True).agg(agg).reset_index().rename(columns={"_bucket": "ts"})
    out["volume"] = out["volume"].astype("int64")
    return out


def build_daily(base: pd.DataFrame) -> pd.DataFrame:
    """One row per session, indexed by session date (datetime.date)."""
    if base.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    day = base["ts"].dt.date
    out = base.groupby(day, sort=True).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    out.index.name = "day"
    return out
