"""Corporate-action adjustment and detection (config/corporate_actions.yaml)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import pandas as pd

from trademind.services.market_data.source import DataSource
from trademind.shared.clock import IST
from trademind.shared.config import CorporateAction

PRICE_COLUMNS = ["open", "high", "low", "close"]
JUMP_THRESHOLD = 0.20  # NSE large caps practically never gap this far for real


def adjust_bars(df: pd.DataFrame, actions: Iterable[CorporateAction]) -> pd.DataFrame:
    """Back-adjust bars before each action's ex-date so prices are comparable across it."""
    acts = list(actions)
    if df.empty or not acts:
        return df
    out = df.copy()
    days = out["ts"].dt.tz_convert(IST).dt.date
    for a in acts:
        before = (days < a.ex_date).to_numpy()
        out.loc[before, PRICE_COLUMNS] = out.loc[before, PRICE_COLUMNS] / a.ratio
        out.loc[before, "volume"] = (out.loc[before, "volume"] * a.ratio).round().astype(out["volume"].dtype)
    return out


def overnight_jumps(df: pd.DataFrame, threshold: float = JUMP_THRESHOLD) -> list[tuple[date, float]]:
    """Days whose first open differs from the previous day's last close by more than `threshold`."""
    if df.empty:
        return []
    ts = df["ts"].dt.tz_convert(IST)
    by_day = df.assign(day=ts.dt.date).groupby("day", sort=True)
    first_open, last_close = by_day["open"].first(), by_day["close"].last()
    ratio = first_open / last_close.shift(1)
    jumps = ratio[(ratio - 1).abs() > threshold]
    return [(d, float(r)) for d, r in jumps.items()]


class AdjustedSource:
    """Wraps a source or store; applies the configured actions for each symbol on read."""

    def __init__(self, base: DataSource, actions: Iterable[CorporateAction]) -> None:
        self.base = base
        self.by_symbol: dict[str, list[CorporateAction]] = {}
        for a in actions:
            self.by_symbol.setdefault(a.symbol, []).append(a)

    def get_bars(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        return adjust_bars(self.base.get_bars(symbol, interval, start, end), self.by_symbol.get(symbol, []))

    def read(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        return self.get_bars(symbol, interval, start, end)

    def __getattr__(self, name: str):  # sessions(), path(), write() of a wrapped store
        return getattr(self.base, name)
