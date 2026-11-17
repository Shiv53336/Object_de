"""Morning readiness check (`trademind preflight`, docs/TESTING.md).

Each check returns OK, WARN or FAIL with one line of detail. FAIL means the day's run would not work;
WARN means it would run but something deserves a look. Network checks (Kite profile, clock skew)
are done by the CLI and passed in, so everything here is testable offline.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd

from trademind.services.broker_gateway.kite import TokenStore
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.market_data.store import ParquetStore
from trademind.shared.clock import at
from trademind.shared.config import AppConfig, RuntimePaths

OK, WARN, FAIL = "OK", "WARN", "FAIL"
MIN_SESSIONS = 30  # the live runner keeps the last 30 sessions of history


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def previous_weekday(day: date) -> date:
    d = day - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def check_python() -> Check:
    v = sys.version_info
    status = OK if v >= (3, 11) else FAIL
    return Check("python", status, f"{v.major}.{v.minor}.{v.micro} on {sys.platform}")


def check_config(cfg: AppConfig) -> Check:
    s = cfg.settings
    enabled = [x for x in cfg.strategies.instances if x.enabled]
    if not enabled:
        return Check("config", FAIL, "no enabled strategy instances")
    return Check("config", OK, f"{len(enabled)} instances, mode {s.execution.mode}, "
                               f"holdout from {s.validation.holdout_start}")


def check_env(env: Mapping[str, str], purpose: str) -> list[Check]:
    out = []
    missing = [k for k in ("KITE_API_KEY", "KITE_API_SECRET") if not env.get(k)]
    if missing:
        status = FAIL if purpose == "paper" else WARN
        out.append(Check("kite keys", status, f"missing {', '.join(missing)} in .env"))
    else:
        out.append(Check("kite keys", OK, "KITE_API_KEY and KITE_API_SECRET set"))
    if env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID"):
        out.append(Check("telegram", OK, "alerts and Telegram login enabled"))
    else:
        out.append(Check("telegram", WARN, "not set: no alerts; log in with `trademind login`"))
    return out


def check_token(paths: RuntimePaths, today: date, purpose: str) -> Check:
    if TokenStore(paths.data_dir / "kite_token.json").load(today):
        return Check("kite login", OK, f"session saved for {today}")
    status = FAIL if purpose == "paper" else WARN
    return Check("kite login", status, "no session for today: run `trademind login`")


def check_history(cfg: AppConfig, store: ParquetStore, today: date, purpose: str) -> list[Check]:
    s = cfg.settings
    interval = s.session.base_interval
    want_last = previous_weekday(today)
    missing, stale, short, lasts = [], [], [], []
    for sym in build_instruments(s):
        sessions = [d for d in store.sessions(sym, interval) if d < today]
        if not sessions:
            missing.append(sym)
            continue
        lasts.append(sessions[-1])
        if sessions[-1] < want_last:
            stale.append(f"{sym} ({sessions[-1]})")
        if len(sessions) < MIN_SESSIONS:
            short.append(f"{sym} ({len(sessions)})")
    out = []
    if s.market_symbol in missing:
        out.append(Check("history", FAIL, f"no bars for {s.market_symbol}: run `trademind data download`"))
    elif missing:
        out.append(Check("history", WARN, f"no bars, will be skipped: {', '.join(missing)}"))
    else:
        out.append(Check("history", OK, f"{len(lasts)} symbols, latest session {max(lasts)}"))
    if stale:
        status = WARN if purpose == "paper" else OK
        out.append(Check("freshness", status, f"older than {want_last} (holiday, or download needed): "
                                              + ", ".join(stale)))
    if short:
        out.append(Check("depth", WARN, f"fewer than {MIN_SESSIONS} sessions: {', '.join(short)}"))
    return out


def check_journal(ping: Callable[[], bool]) -> Check:
    try:
        ping()
    except Exception as exc:  # any driver error means the journal is unusable
        return Check("journal", FAIL, f"database not reachable: {type(exc).__name__}: {exc}")
    return Check("journal", OK, "database reachable")


def check_disk(path: Path, free_bytes: int | None = None) -> Check:
    probe = path if path.exists() else path.resolve().parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    free = shutil.disk_usage(probe).free if free_bytes is None else free_bytes
    gb = free / 1e9
    status = FAIL if gb < 0.5 else WARN if gb < 2 else OK
    return Check("disk", status, f"{gb:.1f} GB free")


def check_session_time(cfg: AppConfig, now: pd.Timestamp) -> Check:
    s = cfg.settings.session
    today = now.date()
    if today.weekday() >= 5:
        return Check("market day", WARN, f"{today:%A}: not a trading day")
    if now >= at(today, s.close):
        return Check("market day", WARN, "today's session is over")
    if now >= at(today, s.open):
        return Check("market day", WARN, "session already open: the run will backfill missed minutes")
    return Check("market day", OK, f"session opens at {s.open:%H:%M}")


def check_timezone(local_offset: timedelta | None) -> Check:
    """Scheduled tasks use the computer's local time, so it must be India Standard Time."""
    if local_offset == timedelta(hours=5, minutes=30):
        return Check("time zone", OK, "local time is IST (UTC+05:30)")
    return Check("time zone", WARN, f"local offset {local_offset}: set Windows to India Standard Time, "
                                    "or the 08:45 task runs at the wrong moment")


def check_power(on_battery: bool | None) -> Check | None:
    if on_battery is None:
        return None
    if on_battery:
        return Check("power", WARN, "on battery: plug the laptop in for the session")
    return Check("power", OK, "on mains power")


def check_clock(server_date_header: str | None, local_now: pd.Timestamp) -> Check:
    """Compare the local clock with a server's HTTP Date header (one-second resolution)."""
    if not server_date_header:
        return Check("clock", WARN, "could not read server time")
    server = pd.Timestamp(parsedate_to_datetime(server_date_header))
    skew = (local_now.tz_convert("UTC") - server.tz_convert("UTC")).total_seconds()
    status = FAIL if abs(skew) > 10 else WARN if abs(skew) > 2 else OK
    return Check("clock", status, f"local clock {skew:+.0f}s vs server (bars close on the minute)")


def summarize(checks: list[Check]) -> tuple[str, int]:
    width = max(len(c.name) for c in checks)
    lines = [f"{c.status:4s}  {c.name:{width}s}  {c.detail}" for c in checks]
    fails = sum(c.status == FAIL for c in checks)
    warns = sum(c.status == WARN for c in checks)
    verdict = "READY" if not fails else f"NOT READY: {fails} failed"
    lines += ["", verdict + (f" ({warns} warnings)" if warns else "")]
    return "\n".join(lines), (1 if fails else 0)
