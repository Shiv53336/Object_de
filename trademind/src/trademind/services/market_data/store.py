"""Parquet bar store and CSV source (PLAN 3). Layout: {root}/{interval}/{SYMBOL}.parquet."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from trademind.services.market_data.source import empty_bars, filter_dates, normalize_bars
from trademind.shared.clock import file_symbol


class ParquetStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path(self, symbol: str, interval: str) -> Path:
        return self.root / interval / f"{file_symbol(symbol)}.parquet"

    def write(self, symbol: str, interval: str, df: pd.DataFrame) -> int:
        """Merge on ts (new rows win). Returns the total row count."""
        new = normalize_bars(df)
        p = self.path(symbol, interval)
        if p.exists():
            old = normalize_bars(pd.read_parquet(p))
            merged = pd.concat([old, new], ignore_index=True)
            new = normalize_bars(merged)
        p.parent.mkdir(parents=True, exist_ok=True)
        new.to_parquet(p, index=False)
        return len(new)

    def read(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        p = self.path(symbol, interval)
        if not p.exists():
            return empty_bars()
        return filter_dates(normalize_bars(pd.read_parquet(p)), start, end)

    def sessions(self, symbol: str, interval: str) -> list[date]:
        p = self.path(symbol, interval)
        if not p.exists():
            return []
        ts = normalize_bars(pd.read_parquet(p))["ts"]
        return sorted(set(ts.dt.date))

    def get_bars(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        return self.read(symbol, interval, start, end)


class CsvSource:
    """Reads {root}/{interval}/{SYMBOL}.csv with columns ts,open,high,low,close,volume[,oi]."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def get_bars(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        p = self.root / interval / f"{file_symbol(symbol)}.csv"
        if not p.exists():
            return empty_bars()
        return filter_dates(normalize_bars(pd.read_csv(p)), start, end)
