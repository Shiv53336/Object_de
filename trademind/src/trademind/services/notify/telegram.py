"""Telegram alerts (T10). A no-op without TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID; never raises."""

from __future__ import annotations

import logging
import os

import httpx

from trademind.shared.models import Trade

log = logging.getLogger(__name__)
API = "https://api.telegram.org/bot{token}/sendMessage"
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
