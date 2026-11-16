"""Causal intraday features (STRATEGIES A.1, A.2). Row i depends only on rows <= i."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trademind.shared.models import Instrument


def add_base_features(base: pd.DataFrame, instrument: Instrument) -> pd.DataFrame:
    """vwap (with typical-price fallback for no-volume symbols), day_high, day_low."""
    df = base.copy()
    if df.empty:
        for col in ("vwap", "day_high", "day_low"):
            df[col] = pd.Series([], dtype="float64")
        return df
    key = df["ts"].dt.normalize()
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    avg_tp = tp.groupby(key).cumsum() / (tp.groupby(key).cumcount() + 1)
    if instrument.has_volume:
        vol = df["volume"].astype("float64")
        cum_v = vol.groupby(key).cumsum()
        cum_pv = (tp * vol).groupby(key).cumsum()
        vwap = cum_pv / cum_v.where(cum_v > 0)
        df["vwap"] = vwap.where(cum_v > 0, avg_tp)
    else:
        df["vwap"] = avg_tp
    df["day_high"] = df["high"].groupby(key).cummax()
    df["day_low"] = df["low"].groupby(key).cummin()
    return df


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    hl = df["high"] - df["low"]
    hc = (df["high"] - prev_close).abs()
    lc = (df["low"] - prev_close).abs()
    return pd.Series(np.fmax(hl, np.fmax(hc, lc)), index=df.index)


def add_tf_features(tf: pd.DataFrame, instrument: Instrument) -> pd.DataFrame:
    """atr14 (continuous across sessions) and tod_rvol (vs same time of day, previous sessions)."""
    df = tf.copy()
    if df.empty:
        df["atr14"] = pd.Series([], dtype="float64")
        df["tod_rvol"] = pd.Series([], dtype="float64")
        return df
    df["atr14"] = true_range(df).rolling(14, min_periods=14).mean()
    if not instrument.has_volume:
        df["tod_rvol"] = np.nan
        return df
    day = df["ts"].dt.normalize()
    tod = df["ts"] - day
    piv = pd.DataFrame(
        {"day": day, "tod": tod, "v": df["volume"].astype("float64")}
    ).pivot(index="day", columns="tod", values="v")
    mean = piv.rolling(20, min_periods=10).mean().shift(1)
    mean = mean.where(mean > 0)
    m = mean.to_numpy()[piv.index.get_indexer(day), piv.columns.get_indexer(tod)]
    df["tod_rvol"] = df["volume"].to_numpy(dtype="float64") / m
    return df
