"""Higher-timeframe trend labels attached to base rows (STRATEGIES A.7)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trademind.services.market_data.resample import resample_bars
from trademind.shared.clock import IST
from trademind.shared.config import SessionConfig

HTF = ((15, "trend_15m"), (60, "trend_60m"))
_NS = f"datetime64[ns, {IST}]"


def trend_labels(bars: pd.DataFrame) -> np.ndarray:
    close = bars["close"].to_numpy(dtype="float64")
    sma = pd.Series(close).rolling(20, min_periods=20).mean().to_numpy()
    sma_prev = np.concatenate([np.full(5, np.nan), sma[:-5]]) if len(sma) > 5 else np.full_like(sma, np.nan)
    j = np.arange(len(close))
    up = (close > sma) & (sma > sma_prev)
    down = (close < sma) & (sma < sma_prev)
    out = np.where(up, "up", np.where(down, "down", "flat")).astype(object)
    out[j < 24] = "unknown"
    return out


def add_htf_trend(base: pd.DataFrame, session: SessionConfig) -> pd.DataFrame:
    """Label each base row with the trend of the last H-minute bar already closed by its close."""
    df = base.copy()
    if df.empty:
        for _, col in HTF:
            df[col] = pd.Series([], dtype=object)
        return df
    base_close = pd.DataFrame(
        {"close_time": (df["ts"] + pd.Timedelta(minutes=session.base_minutes)).astype(_NS)}
    )
    ohlcv = df[["ts", "open", "high", "low", "close", "volume"]]
    for minutes, col in HTF:
        if minutes % session.base_minutes:
            df[col] = "unknown"
            continue
        r = resample_bars(ohlcv, minutes, session)
        labels = pd.DataFrame(
            {
                "close_time": (r["ts"] + pd.Timedelta(minutes=minutes)).astype(_NS),
                col: trend_labels(r),
            }
        )
        merged = pd.merge_asof(base_close, labels, on="close_time", direction="backward")
        df[col] = merged[col].fillna("unknown").to_numpy(dtype=object)
    return df
