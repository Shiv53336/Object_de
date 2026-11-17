"""Zerodha Kite Connect, read-only (BLUEPRINT 5.1, PLAN 10).

Every call goes through `ReadOnlyClient`, which exposes an explicit allowlist of read
methods. Anything else raises, so this module cannot send, change or cancel an order.
The real `kiteconnect` client is created lazily so tests and backtests never need it.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from trademind.services.market_data.source import empty_bars, normalize_bars
from trademind.shared.clock import IST
from trademind.shared.exceptions import DataError, TrademindError

log = logging.getLogger(__name__)

ALLOWED_METHODS = frozenset(
    {
        "login_url",
        "generate_session",
        "set_access_token",
        "profile",
        "instruments",
        "historical_data",
        "quote",
        "ltp",
    }
)

# Kite interval names and maximum days per historical request (PLAN 10).
KITE_INTERVALS = {
    "1minute": ("minute", 60),
    "3minute": ("3minute", 100),
    "5minute": ("5minute", 100),
    "10minute": ("10minute", 100),
    "15minute": ("15minute", 200),
    "30minute": ("30minute", 200),
    "60minute": ("60minute", 400),
    "day": ("day", 2000),
}

# Futures/options underlying name in the NFO dump for each index symbol.
INDEX_UNDERLYING = {"NIFTY 50": "NIFTY", "NIFTY BANK": "BANKNIFTY"}


class AuthError(TrademindError):
    pass


class ReadOnlyClient:
    """Wraps a Kite client and refuses every method outside ALLOWED_METHODS."""

    def __init__(self, client: Any) -> None:
        object.__setattr__(self, "_client", client)

    def __getattr__(self, name: str) -> Any:
        if name not in ALLOWED_METHODS:
            raise AttributeError(f"{name!r} is not available: the Kite gateway is read-only")
        return getattr(self._client, name)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("ReadOnlyClient is immutable")


def make_kite_client(api_key: str, access_token: str | None = None) -> ReadOnlyClient:
    from kiteconnect import KiteConnect  # imported lazily: only live use needs it

    client = KiteConnect(api_key=api_key)
    if access_token:
        client.set_access_token(access_token)
    return ReadOnlyClient(client)


# ---- access token ------------------------------------------------------------------------


@dataclass
class TokenStore:
    """Access tokens expire daily, so a token saved on an earlier date is treated as invalid."""

    path: Path

    def save(self, access_token: str, day: date) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"access_token": access_token, "date": day.isoformat()})
        self.path.write_text(payload, encoding="utf-8")
        self.path.chmod(0o600)

    def load(self, today: date) -> str | None:
        if not self.path.exists():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("date") != today.isoformat():
            return None
        return data.get("access_token") or None


# ---- gateway -----------------------------------------------------------------------------


def _retryable(exc: Exception) -> bool:
    name = type(exc).__name__
    return name == "NetworkException" or "too many requests" in str(exc).lower()


class KiteGateway:
    def __init__(
        self,
        client: Any,
        *,
        max_rps: float = 3.0,
        retries: int = 3,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client if isinstance(client, ReadOnlyClient) else ReadOnlyClient(client)
        self.min_gap = 1.0 / max_rps
        self.retries = retries
        self.clock = clock
        self.sleep = sleep
        self._last: float | None = None

    def _throttle(self) -> None:
        now = self.clock()
        if self._last is not None:
            wait = self.min_gap - (now - self._last)
            if wait > 0:
                self.sleep(wait)
                now = self.clock()
        self._last = now

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        delay = 1.0
        for attempt in range(self.retries + 1):
            self._throttle()
            try:
                return getattr(self.client, method)(*args, **kwargs)
            except Exception as exc:
                if type(exc).__name__ == "TokenException":
                    raise AuthError("Kite session expired: run `trademind login`") from exc
                if attempt < self.retries and _retryable(exc):
                    log.warning("kite retry", extra={"method": method, "attempt": attempt + 1})
                    self.sleep(delay)
                    delay *= 2
                    continue
                raise

    def login_url(self) -> str:
        return self.client.login_url()

    def create_session(self, request_token: str, api_secret: str) -> str:
        data = self._call("generate_session", request_token, api_secret=api_secret)
        return data["access_token"]

    def profile(self) -> dict:
        return self._call("profile")

    def instruments(self, exchange: str | None = None) -> pd.DataFrame:
        rows = self._call("instruments", exchange) if exchange else self._call("instruments")
        return pd.DataFrame(rows)

    def historical(self, token: int, start: datetime, end: datetime, kite_interval: str) -> list[dict]:
        return self._call("historical_data", token, start, end, kite_interval)


# ---- instruments -------------------------------------------------------------------------


class InstrumentDirectory:
    """Symbol -> token, lot size, tick size and expiries from the daily instruments dump."""

    def __init__(self, dump: pd.DataFrame) -> None:
        self.dump = dump

    @classmethod
    def load_or_fetch(cls, gateway: KiteGateway, data_dir: Path, today: date) -> InstrumentDirectory:
        path = data_dir / f"instruments-{today.isoformat()}.csv"
        if path.exists():
            df = pd.read_csv(path)
        else:
            nse = gateway.instruments("NSE")
            nfo = gateway.instruments("NFO")
            df = pd.concat([nse, nfo], ignore_index=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            df.to_csv(path, index=False)
        df["expiry"] = pd.to_datetime(df["expiry"], errors="coerce").dt.date
        return cls(df)

    def token(self, symbol: str, exchange: str = "NSE") -> int:
        hit = self.dump[(self.dump["exchange"] == exchange) & (self.dump["tradingsymbol"] == symbol)]
        if hit.empty:
            raise DataError(f"{exchange}:{symbol} not found in the instruments dump")
        return int(hit["instrument_token"].iloc[0])

    def lot_and_tick(self, symbol: str, kind: str, today: date) -> tuple[int, float] | None:
        """Index: lot size of the nearest index future. Stock: cash segment tick size, lot 1."""
        if kind == "index":
            name = INDEX_UNDERLYING.get(symbol)
            fut = self.dump[
                (self.dump["exchange"] == "NFO")
                & (self.dump["name"] == name)
                & (self.dump["instrument_type"] == "FUT")
                & (self.dump["expiry"] >= today)
            ].sort_values("expiry")
            if fut.empty:
                return None
            return int(fut["lot_size"].iloc[0]), float(fut["tick_size"].iloc[0])
        hit = self.dump[(self.dump["exchange"] == "NSE") & (self.dump["tradingsymbol"] == symbol)]
        return None if hit.empty else (1, float(hit["tick_size"].iloc[0]))

    def expiries(self, today: date) -> dict[str, list[date]]:
        """Upcoming expiry dates: index options per index, and stock futures for 'STOCKS'."""
        nfo = self.dump[(self.dump["exchange"] == "NFO") & (self.dump["expiry"].notna())]
        nfo = nfo[nfo["expiry"] >= today]
        out: dict[str, list[date]] = {}
        for symbol, name in INDEX_UNDERLYING.items():
            ds = nfo[(nfo["name"] == name) & nfo["instrument_type"].isin(["CE", "PE", "FUT"])]["expiry"]
            out[symbol] = sorted(set(ds))
        stock_names = set(INDEX_UNDERLYING.values()) | {"FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}
        stk = nfo[(nfo["instrument_type"] == "FUT") & ~nfo["name"].isin(stock_names)]["expiry"]
        out["STOCKS"] = sorted(set(stk))
        return out


# ---- historical data source --------------------------------------------------------------


def date_chunks(start: date, end: date, max_days: int) -> list[tuple[date, date]]:
    """Inclusive [start, end] split into consecutive inclusive windows of at most max_days."""
    out, cur = [], start
    while cur <= end:
        stop = min(end, cur + timedelta(days=max_days - 1))
        out.append((cur, stop))
        cur = stop + timedelta(days=1)
    return out


class KiteSource:
    """DataSource over Kite historical candles."""

    def __init__(self, gateway: KiteGateway, directory: InstrumentDirectory) -> None:
        self.gateway = gateway
        self.directory = directory

    def get_bars(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        if interval not in KITE_INTERVALS:
            raise ValueError(f"unsupported interval {interval!r}")
        kite_interval, max_days = KITE_INTERVALS[interval]
        token = self.directory.token(symbol)
        rows: list[dict] = []
        for a, b in date_chunks(start, end, max_days):
            rows += self.gateway.historical(
                token,
                datetime.combine(a, datetime.min.time()),
                datetime.combine(b, datetime.max.time().replace(microsecond=0)),
                kite_interval,
            )
        if not rows:
            return empty_bars()
        df = pd.DataFrame(rows).rename(columns={"date": "ts"})
        ts = pd.to_datetime(df["ts"])
        df["ts"] = ts.dt.tz_localize(IST) if ts.dt.tz is None else ts.dt.tz_convert(IST)
        return normalize_bars(df)
