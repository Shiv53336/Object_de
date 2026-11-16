"""Feature-complete market data per symbol, sliced per session for the engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from trademind.services.feature_engine.context import (
    DayContext,
    build_day_table,
    clean,
    opening_stats,
)
from trademind.services.feature_engine.htf import add_htf_trend
from trademind.services.feature_engine.indicators import add_base_features, add_tf_features
from trademind.services.market_data.resample import build_daily, resample_bars
from trademind.services.strategy_engine.view import DayFrames
from trademind.shared.config import AppConfig
from trademind.shared.models import Instrument

DAY_TAGS = ("gap_bucket", "daily_trend", "vol_regime", "is_expiry_day")
EOD_TAGS = ("day_type", "day_range_pct")
OR_TAGS = ("or_width_pct", "or_width_bucket")


def day_slices(ts: pd.Series) -> dict[date, tuple[int, int]]:
    """Contiguous row ranges per session date of a sorted ts column."""
    if ts.empty:
        return {}
    days = ts.dt.date.to_numpy()
    change = np.flatnonzero(days[1:] != days[:-1]) + 1
    starts = np.r_[0, change]
    ends = np.r_[change, len(days)]
    return {days[s]: (int(s), int(e)) for s, e in zip(starts, ends, strict=True)}


@dataclass
class SymbolData:
    instrument: Instrument
    base: pd.DataFrame
    tf: dict[int, pd.DataFrame]
    day_table: pd.DataFrame
    or_stats: pd.DataFrame
    base_slices: dict[date, tuple[int, int]]
    tf_slices: dict[int, dict[date, tuple[int, int]]]

    def frames(self, day: date, cfg: AppConfig) -> DayFrames | None:
        if day not in self.base_slices:
            return None
        s, e = self.base_slices[day]
        base = self.base.iloc[s:e].reset_index(drop=True)
        tf: dict[int, pd.DataFrame] = {}
        for minutes, df in self.tf.items():
            a, b = self.tf_slices[minutes].get(day, (0, 0))
            tf[minutes] = df.iloc[a:b].reset_index(drop=True)
        row = self.day_table.loc[day]
        ctx = DayContext(
            day=day,
            symbol=self.instrument.symbol,
            instrument=self.instrument,
            first_open=float(base["open"].iloc[0]),
            prev_close=clean(row["prev_close"]),
            prev_day_high=clean(row["prev_day_high"]),
            prev_day_low=clean(row["prev_day_low"]),
            gap_pct=clean(row["gap_pct"]),
            daily_atr_pct=clean(row["daily_atr_pct"]),
            daily_trend=str(row["daily_trend"]),
            in_play=self.instrument.kind == "index",
            tags={k: row[k] for k in DAY_TAGS},
        )
        return DayFrames(
            symbol=self.instrument.symbol,
            instrument=self.instrument,
            ctx=ctx,
            session=cfg.settings.session,
            base=base,
            tf=tf,
        )

    def opening(self, day: date) -> dict:
        r = self.or_stats.loc[day]
        return {"or_rvol": clean(r["or_rvol"]), **{k: r[k] for k in OR_TAGS}}

    def eod_tags(self, day: date) -> dict:
        r = self.day_table.loc[day]
        return {k: r[k] for k in EOD_TAGS}


def prepare_symbol(
    instrument: Instrument, raw_base: pd.DataFrame, cfg: AppConfig, timeframes: set[int]
) -> SymbolData:
    session = cfg.settings.session
    base = add_htf_trend(add_base_features(raw_base, instrument), session)
    tf = {m: add_tf_features(resample_bars(base, m, session), instrument) for m in sorted(timeframes)}
    daily = build_daily(raw_base)
    day_table = build_day_table(daily, instrument, cfg.expiries)
    or_stats = opening_stats(base, instrument, session, cfg.settings.selector.or_minutes, daily.index)
    return SymbolData(
        instrument=instrument,
        base=base,
        tf=tf,
        day_table=day_table,
        or_stats=or_stats,
        base_slices=day_slices(base["ts"]),
        tf_slices={m: day_slices(df["ts"]) for m, df in tf.items()},
    )
