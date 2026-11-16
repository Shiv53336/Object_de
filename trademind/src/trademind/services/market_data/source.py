"""Bar contract, data-source protocol and validation (PLAN 4.1)."""

from __future__ import annotations

from datetime import date
from typing import Protocol

import numpy as np
import pandas as pd

from trademind.shared.clock import IST, at
from trademind.shared.config import SessionConfig

BAR_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]


def empty_bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.Series([], dtype=f"datetime64[ns, {IST}]"),
            "open": pd.Series([], dtype="float64"),
            "high": pd.Series([], dtype="float64"),
            "low": pd.Series([], dtype="float64"),
            "close": pd.Series([], dtype="float64"),
            "volume": pd.Series([], dtype="int64"),
        }
    )


def normalize_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce the bar contract: IST-aware ts, float prices, int volume, sorted, unique."""
    missing = [c for c in BAR_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"bars missing columns: {missing}")
    if df.empty:
        out = empty_bars()
        if "oi" in df.columns:
            out["oi"] = pd.Series([], dtype="float64")
        return out
    out = df.copy()
    ts = pd.to_datetime(out["ts"])
    ts = ts.dt.tz_localize(IST) if ts.dt.tz is None else ts.dt.tz_convert(IST)
    out["ts"] = ts.astype(f"datetime64[ns, {IST}]")
    for col in ("open", "high", "low", "close"):
        out[col] = out[col].astype("float64")
    out["volume"] = out["volume"].fillna(0).astype("int64")
    if "oi" in out.columns:
        out["oi"] = out["oi"].astype("float64")
    cols = BAR_COLUMNS + (["oi"] if "oi" in out.columns else [])
    out = out[cols].drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    return out


def filter_dates(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df.empty:
        return df
    d = df["ts"].dt.date
    return df[(d >= start) & (d <= end)].reset_index(drop=True)


class DataSource(Protocol):
    def get_bars(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        """Bars for sessions from start to end inclusive; empty typed frame if none."""
        ...


def validate_bars(df: pd.DataFrame, session: SessionConfig, minutes: int) -> list[str]:
    """Human-readable problems; empty list means clean. Missing bars are reported, not errors."""
    problems: list[str] = []
    missing_cols = [c for c in BAR_COLUMNS if c not in df.columns]
    if missing_cols:
        return [f"missing columns: {missing_cols}"]
    if df.empty:
        return problems
    if getattr(df["ts"].dt, "tz", None) is None:
        problems.append("ts is not timezone-aware")
        return problems
    if not df["ts"].is_monotonic_increasing:
        problems.append("ts is not sorted")
    if df["ts"].duplicated().any():
        problems.append(f"{int(df['ts'].duplicated().sum())} duplicate timestamps")
    ts = df["ts"].dt.tz_convert(IST)
    day_open = ts.dt.normalize() + pd.Timedelta(hours=session.open.hour, minutes=session.open.minute)
    offset = (ts - day_open) / pd.Timedelta(minutes=1)
    off_grid = (offset % minutes != 0) | (offset < 0) | (offset >= session.length_minutes)
    if off_grid.any():
        problems.append(f"{int(off_grid.sum())} bars off the {minutes}-minute session grid")
    bad_high = df["high"] < np.maximum(df["open"], df["close"])
    bad_low = df["low"] > np.minimum(df["open"], df["close"])
    if bad_high.any():
        problems.append(f"{int(bad_high.sum())} bars with high below open/close")
    if bad_low.any():
        problems.append(f"{int(bad_low.sum())} bars with low above open/close")
    if (df["volume"] < 0).any():
        problems.append("negative volume")
    expected = session.length_minutes // minutes
    counts = ts.dt.date.value_counts()
    short = counts[counts < expected]
    if len(short):
        worst = short.sort_values().head(3)
        detail = ", ".join(f"{d}: {expected - n} missing" for d, n in worst.items())
        problems.append(f"info: {len(short)} sessions with missing bars ({detail})")
    return problems


def session_open_ts(day: date, session: SessionConfig) -> pd.Timestamp:
    return at(day, session.open)
