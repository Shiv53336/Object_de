"""Telegram alerts (T10). A no-op without TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID; never raises."""

from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Callable

import httpx

from trademind.shared.models import Trade

log = logging.getLogger(__name__)
API = "https://api.telegram.org/bot{token}/sendMessage"
UPDATES = "https://api.telegram.org/bot{token}/getUpdates"
TOKEN_RE = re.compile(r"request_token=([A-Za-z0-9]+)|^\s*([A-Za-z0-9]{20,64})\s*$")
MAX_LEN = 4000


class Notifier:
    def __init__(
        self,
        token: str | None = None,
        chat_id: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")
        self.client = client or httpx.Client(timeout=10)
        self.sent = 0

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            r = self.client.post(
                API.format(token=self.token),
                json={"chat_id": self.chat_id, "text": text[:MAX_LEN], "disable_web_page_preview": True},
            )
            r.raise_for_status()
            self.sent += 1
            return True
        except Exception as exc:  # alerts must never stop trading
            log.warning("telegram send failed", extra={"error": type(exc).__name__})
            return False

    def trade_opened(self, instance_id: str, symbol: str, side: str, qty: int, price: float,
                     stop: float, target: float | None) -> bool:
        tgt = "-" if target is None else f"{target:,.2f}"
        return self.send(
            f"PAPER {side} {symbol} x{qty} @ {price:,.2f}\nstop {stop:,.2f}  target {tgt}\n{instance_id}"
        )

    def trade_closed(self, t: Trade) -> bool:
        return self.send(
            f"PAPER closed {t.symbol} {t.side} {t.exit_reason}\n"
            f"net Rs {t.net_pnl:,.0f}  ({t.r_multiple:+.2f}R)\n{t.instance_id}"
        )

    def daily_summary(self, text: str) -> bool:
        return self.send(text)

    def error(self, text: str) -> bool:
        return self.send(f"TRADEMIND error: {text}")

    # ---- reading replies (used only for the daily Kite login) ------------------------
    def updates(self, offset: int | None, timeout: int = 25) -> list[dict]:
        params: dict = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        try:
            r = self.client.get(UPDATES.format(token=self.token), params=params, timeout=timeout + 10)
            r.raise_for_status()
            return r.json().get("result", [])
        except Exception as exc:
            log.warning("telegram getUpdates failed", extra={"error": type(exc).__name__})
            return []

    def wait_for_request_token(
        self,
        login_url: str,
        timeout_s: float = 1800,
        clock: Callable[[], float] = time.monotonic,
        poll_timeout: int = 25,
    ) -> str | None:
        """Send the Kite login link and wait for the owner to paste back the redirect URL.

        Only messages from the configured chat are accepted. Returns the request_token or None.
        """
        if not self.enabled:
            return None
        offset = None
        for u in self.updates(None, timeout=0):  # skip anything sent before this login
            offset = u["update_id"] + 1
        self.send(
            "TRADEMIND: Kite login needed for today's paper trading.\n"
            f"1. Open: {login_url}\n"
            "2. After logging in, copy the full address of the page you land on "
            "(it contains request_token=...) and send it here."
        )
        deadline = clock() + timeout_s
        while clock() < deadline:
            for u in self.updates(offset, timeout=poll_timeout):
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                if str((msg.get("chat") or {}).get("id")) != str(self.chat_id):
                    continue
                m = TOKEN_RE.search(msg.get("text") or "")
                if m:
                    return m.group(1) or m.group(2)
        self.send("TRADEMIND: no login received in time; paper trading skipped today.")
        return None
