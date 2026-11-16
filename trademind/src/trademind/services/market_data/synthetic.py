"""Deterministic synthetic market data for development and tests (no broker needed).

Daily open/close levels come from a per-symbol random walk over a fixed calendar, with a
shared market factor. Each day's 1-minute path is a Brownian bridge from that day's open
to its close, generated from (seed, symbol, date). Any date range therefore returns
identical bars for the same day. This data has no edge by construction: it is for
exercising the pipeline, not for judging strategies.
"""

from __future__ import annotations

import zlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from trademind.services.market_data.source import empty_bars, normalize_bars
from trademind.shared.clock import session_grid, tf_minutes
from trademind.shared.config import SessionConfig
from trademind.shared.models import Instrument

EPOCH = date(2015, 1, 1)
HORIZON = date(2035, 12, 31)


def _weekdays(start: date, end: date) -> list[date]:
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def make_session(
    day: date,
    closes: list[float],
    session: SessionConfig,
    *,
    first_open: float | None = None,
    volumes: list[int] | None = None,
    wick: float = 0.0005,
    minutes: int | None = None,
) -> pd.DataFrame:
    """Bars on the session grid from a close path (tests). May be a partial session."""
    m = minutes or session.base_minutes
    grid = session_grid(day, session.open, session.close, m)[: len(closes)]
    c = np.asarray(closes, dtype=float)
    o = np.empty_like(c)
    o[0] = first_open if first_open is not None else c[0]
    o[1:] = c[:-1]
    df = pd.DataFrame(
        {
            "ts": grid,
            "open": o,
            "high": np.maximum(o, c) * (1 + wick),
            "low": np.minimum(o, c) * (1 - wick),
            "close": c,
            "volume": volumes if volumes is not None else [1000] * len(c),
        }
    )
    return normalize_bars(df)


def make_bars(
    day: date,
    rows: list[tuple[float, float, float, float, int]],
    session: SessionConfig,
    *,
    start_index: int = 0,
    minutes: int | None = None,
) -> pd.DataFrame:
    """Explicit OHLCV rows on consecutive grid slots starting at start_index (tests)."""
    m = minutes or session.base_minutes
    grid = session_grid(day, session.open, session.close, m)[start_index : start_index + len(rows)]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])
    df.insert(0, "ts", grid)
    return normalize_bars(df)


class SyntheticSource:
    def __init__(
        self,
        seed: int,
        instruments: dict[str, Instrument],
        session: SessionConfig,
        market_symbol: str = "NIFTY 50",
    ) -> None:
        self.seed = seed
        self.instruments = instruments
        self.session = session
        self.market_symbol = market_symbol
        self._calendar = _weekdays(EPOCH, HORIZON)
        self._index = {d: i for i, d in enumerate(self._calendar)}
        self._daily: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        n = len(self._calendar)
        mrng = np.random.default_rng([seed, 0])
        self._m_ret = mrng.normal(0.0003, 0.009, n)
        self._m_gap = mrng.normal(0.0, 0.003, n)

    @staticmethod
    def _key(symbol: str) -> int:
        return zlib.crc32(symbol.encode())

    def _daily_path(self, symbol: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if symbol in self._daily:
            return self._daily[symbol]
        key = self._key(symbol)
        rng = np.random.default_rng([self.seed, key])
        n = len(self._calendar)
        inst = self.instruments[symbol]
        if symbol == self.market_symbol:
            ret, gap, start = self._m_ret, self._m_gap, 24000.0
        elif inst.kind == "index":
            ret = 1.2 * self._m_ret + rng.normal(0, 0.004, n)
            gap = 1.2 * self._m_gap + rng.normal(0, 0.002, n)
            start = 52000.0
        else:
            ret = 0.9 * self._m_ret + rng.normal(0, 0.012, n)
            gap = 0.9 * self._m_gap + rng.normal(0, 0.005, n)
            start = 500.0 + (key % 2500)
        log_close = np.log(start) + np.cumsum(gap + ret)
        log_open = log_close - ret
        activity = rng.lognormal(0.0, 0.45, n) * (1 + 25 * np.abs(ret + gap))
        self._daily[symbol] = (log_open, log_close, activity)
        return self._daily[symbol]

    def _day_bars(self, symbol: str, day: date) -> pd.DataFrame:
        i = self._index[day]
        log_open, log_close, activity = self._daily_path(symbol)
        inst = self.instruments[symbol]
        m = self.session.base_minutes
        grid = session_grid(day, self.session.open, self.session.close, m)
        n = len(grid)
        rng = np.random.default_rng([self.seed, self._key(symbol), day.toordinal()])
        daily_sigma = 0.008 if inst.kind == "index" else 0.015
        steps = rng.normal(0.0, daily_sigma / np.sqrt(n), n)
        w = np.cumsum(steps)
        k = np.arange(1, n + 1)
        lo, lc = log_open[i], log_close[i]
        path = lo + (lc - lo) * k / n + (w - k / n * w[-1])
        close = np.exp(path)
        open_ = np.empty(n)
        open_[0] = np.exp(lo)
        open_[1:] = close[:-1]
        wick_scale = daily_sigma / np.sqrt(n)
        high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, wick_scale, n)))
        low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, wick_scale, n)))
        if inst.has_volume:
            u = 1.0 + 1.5 * ((k - n / 2) / (n / 2)) ** 2
            base = 2000 * m
            volume = (base * activity[i] * u * rng.lognormal(0, 0.3, n)).astype("int64")
        else:
            volume = np.zeros(n, dtype="int64")
        return pd.DataFrame(
            {"ts": grid, "open": open_, "high": high, "low": low, "close": close, "volume": volume}
        )

    def get_bars(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        if symbol not in self.instruments:
            return empty_bars()
        if tf_minutes(interval) != self.session.base_minutes:
            raise ValueError("SyntheticSource only serves the base interval")
        days = [d for d in _weekdays(max(start, EPOCH), min(end, HORIZON))]
        if not days:
            return empty_bars()
        frames = [self._day_bars(symbol, d) for d in days]
        return normalize_bars(pd.concat(frames, ignore_index=True))
