"""Day context and context tags (STRATEGIES A.4, A.5, Part B).

Every per-day value uses previous sessions only, except gap_pct (today's first open) and the
opening-range values, which the engine reveals at selection time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time

import numpy as np
import pandas as pd

from trademind.shared.config import SessionConfig
from trademind.shared.models import Instrument


@dataclass(slots=True)
class DayContext:
    day: date
    symbol: str
    instrument: Instrument
    first_open: float
    prev_close: float | None
    prev_day_high: float | None
    prev_day_low: float | None
    gap_pct: float | None
    daily_atr_pct: float | None
    daily_trend: str
    or_rvol: float | None = None  # set by the engine at selection time
    in_play: bool = False  # set by the engine at selection time (always True for indices)
    tags: dict = field(default_factory=dict)


def clean(x: object) -> float | None:
    """NaN/inf/None -> None, numbers -> float."""
    if x is None:
        return None
    try:
        f = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def expiry_key(instrument: Instrument) -> str:
    return instrument.symbol if instrument.kind == "index" else "STOCKS"


def build_day_table(
    daily: pd.DataFrame, instrument: Instrument, expiries: dict[str, list[date]]
) -> pd.DataFrame:
    """Per-session context, indexed like `daily` (session date)."""
    d = daily
    out = pd.DataFrame(index=d.index)
    n_prev = np.arange(len(d))
    prev_close = d["close"].shift(1)
    out["prev_close"] = prev_close
    out["prev_day_high"] = d["high"].shift(1)
    out["prev_day_low"] = d["low"].shift(1)
    out["first_open"] = d["open"]
    out["gap_pct"] = (d["open"] - prev_close) / prev_close * 100

    hl = d["high"] - d["low"]
    tr = pd.Series(
        np.fmax(hl, np.fmax((d["high"] - prev_close).abs(), (d["low"] - prev_close).abs())),
        index=d.index,
    )
    atr_pct = tr.rolling(14, min_periods=14).mean().shift(1) / prev_close * 100
    out["daily_atr_pct"] = atr_pct.where(n_prev >= 15)

    sma20 = d["close"].rolling(20, min_periods=20).mean().shift(1)
    sma50 = d["close"].rolling(50, min_periods=50).mean().shift(1)
    trend = np.where(
        (prev_close > sma20) & (sma20 > sma50),
        "up",
        np.where((prev_close < sma20) & (sma20 < sma50), "down", "flat"),
    ).astype(object)
    trend[n_prev < 50] = "unknown"
    out["daily_trend"] = trend

    med = out["daily_atr_pct"].rolling(100, min_periods=30).median().shift(1)
    ratio = out["daily_atr_pct"] / med
    out["vol_regime"] = np.where(
        ratio.isna(), "unknown", np.where(ratio < 0.8, "low", np.where(ratio > 1.2, "high", "normal"))
    )
    g = out["gap_pct"]
    out["gap_bucket"] = np.where(
        g.isna(), "unknown", np.where(g > 0.4, "gap_up", np.where(g < -0.4, "gap_down", "flat"))
    )

    exp = set(expiries.get(expiry_key(instrument), []))
    years = {e.year for e in exp}
    out["is_expiry_day"] = [
        ("true" if day in exp else "false") if day.year in years else "unknown" for day in d.index
    ]

    rng = hl
    body = (d["close"] - d["open"]).abs() / rng.where(rng > 0)
    close_pos = (d["close"] - d["low"]) / rng.where(rng > 0)
    day_type = np.where(
        (body >= 0.6) & (close_pos >= 0.75),
        "trend_up",
        np.where(
            (body >= 0.6) & (close_pos <= 0.25),
            "trend_down",
            np.where(body <= 0.3, "range", "mixed"),
        ),
    ).astype(object)
    day_type[(rng <= 0).to_numpy()] = "flat"
    out["day_type"] = day_type
    out["day_range_pct"] = hl / d["open"] * 100
    return out


def opening_stats(
    base: pd.DataFrame,
    instrument: Instrument,
    session: SessionConfig,
    or_minutes: int,
    days: pd.Index,
) -> pd.DataFrame:
    """Opening-range values per session, revealed by the engine at selection time."""
    ts = base["ts"]
    day_open = ts.dt.normalize() + pd.Timedelta(hours=session.open.hour, minutes=session.open.minute)
    in_or = (ts < day_open + pd.Timedelta(minutes=or_minutes)).to_numpy()
    sub = base[in_or]
    st = sub.groupby(sub["ts"].dt.date).agg(
        or_high=("high", "max"), or_low=("low", "min"), or_volume=("volume", "sum")
    )
    st = st.reindex(days)
    if instrument.has_volume:
        mean = st["or_volume"].rolling(20, min_periods=10).mean().shift(1)
        st["or_rvol"] = st["or_volume"] / mean.where(mean > 0)
    else:
        st["or_rvol"] = np.nan
    mid = (st["or_high"] + st["or_low"]) / 2
    st["or_width_pct"] = (st["or_high"] - st["or_low"]) / mid * 100
    med = st["or_width_pct"].rolling(20, min_periods=10).median().shift(1)
    ratio = st["or_width_pct"] / med
    st["or_width_bucket"] = np.where(
        ratio.isna(), "unknown", np.where(ratio < 0.7, "narrow", np.where(ratio > 1.3, "wide", "normal"))
    )
    return st


def market_regime(market_tags: dict) -> str:
    """BLUEPRINT 5.7 regime label from session-start facts about the market symbol only.

    Priority: unknown inputs -> UNCLASSIFIED; high volatility; trend up or down; low volatility;
    otherwise SIDEWAYS. Expiry is tagged separately (is_expiry_day).
    """
    vol, trend = market_tags.get("vol_regime"), market_tags.get("daily_trend")
    if vol in (None, "unknown") or trend in (None, "unknown"):
        return "UNCLASSIFIED"
    if vol == "high":
        return "HIGH_VOLATILITY"
    if trend == "up":
        return "BULLISH_TREND"
    if trend == "down":
        return "BEARISH_TREND"
    if vol == "low":
        return "LOW_VOLATILITY"
    return "SIDEWAYS"


TIME_BUCKETS = (
    (time(9, 15), time(10, 0), "open"),
    (time(10, 0), time(11, 30), "morning"),
    (time(11, 30), time(13, 30), "midday"),
    (time(13, 30), time(15, 30), "afternoon"),
)


def time_bucket(t: time) -> str:
    for start, end, name in TIME_BUCKETS:
        if start <= t < end:
            return name
    return "other"


def trade_tags(entry_ts: pd.Timestamp, features: dict, instrument: Instrument, timeframe: str) -> dict:
    mav = features.get("market_above_vwap")
    return {
        "timeframe": timeframe,
        "time_bucket": time_bucket(entry_ts.time()),
        "market_trend_at_entry": "unknown" if mav is None else ("above_vwap" if mav else "below_vwap"),
        "trend_15m_at_entry": features.get("trend_15m") or "unknown",
        "trend_60m_at_entry": features.get("trend_60m") or "unknown",
        "sim_kind": "index_as_future" if instrument.kind == "index" else "direct",
        "vwap_kind": "vwap" if instrument.has_volume else "avg_price",
    }
