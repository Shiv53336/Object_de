"""Kite WebSocket ticks -> LivePaperRunner (read-only market data)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

import pandas as pd

from trademind.services.execution.live_paper import Tick
from trademind.shared.clock import IST

log = logging.getLogger(__name__)


def convert_tick(tick: dict, token_to_symbol: dict[int, str], received_at: pd.Timestamp) -> Tick | None:
    sym = token_to_symbol.get(int(tick.get("instrument_token", -1)))
    price = tick.get("last_price")
    if sym is None or price is None:
        return None
    raw = tick.get("exchange_timestamp") or tick.get("last_trade_time")
    if isinstance(raw, datetime):
        ts = pd.Timestamp(raw)
        ts = ts.tz_localize(IST) if ts.tzinfo is None else ts.tz_convert(IST)
    else:
        ts = received_at
    cum = tick.get("volume_traded")
    return sym, ts, float(price), None if cum is None else int(cum)


class KiteTickStream:
    def __init__(
        self,
        api_key: str,
        access_token: str,
        token_to_symbol: dict[int, str],
        on_ticks: Callable[[list[Tick]], None],
        now: Callable[[], pd.Timestamp],
    ) -> None:
        self.api_key, self.access_token = api_key, access_token
        self.token_to_symbol = token_to_symbol
        self.sink = on_ticks
        self.now = now
        self._ws = None
        self.reconnects = 0

    def start(self) -> None:
        from kiteconnect import KiteTicker  # lazily: only live use needs it

        ws = KiteTicker(self.api_key, self.access_token)
        ws.on_connect = self._on_connect
        ws.on_ticks = self._on_ticks
        ws.on_reconnect = self._on_reconnect
        ws.on_error = lambda _ws, code, reason: log.warning("ticker error", extra={"code": code})
        ws.on_close = lambda _ws, code, reason: log.info("ticker closed", extra={"code": code})
        self._ws = ws
        ws.connect(threaded=True)

    def _on_connect(self, ws, response) -> None:  # noqa: ANN001
        tokens = list(self.token_to_symbol)
        ws.subscribe(tokens)
        ws.set_mode(ws.MODE_FULL, tokens)

    def _on_reconnect(self, ws, attempts: int) -> None:  # noqa: ANN001
        self.reconnects = attempts
        log.warning("ticker reconnecting", extra={"attempt": attempts})

    def _on_ticks(self, ws, ticks: list[dict]) -> None:  # noqa: ANN001
        now = self.now()
        out = [t for t in (convert_tick(x, self.token_to_symbol, now) for x in ticks) if t is not None]
        if out:
            self.sink(out)

    def stop(self) -> None:
        if self._ws is not None:
            self._ws.close()
