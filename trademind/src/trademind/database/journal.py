"""Journal repository: every signal (approved or not), trade, day context and trial."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, func, insert, select, update
from sqlalchemy.engine import Engine

from trademind.database import models as m
from trademind.shared.clock import IST
from trademind.shared.models import Trade

TS_COLUMNS = ("ts", "signal_ts", "entry_ts", "exit_ts", "started_at", "finished_at", "created_at")


def jsonable(value: Any) -> Any:
    """Make features/tags safe for JSON columns: NaN/inf -> None, numpy -> python."""
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, pd.Timestamp | datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def to_utc(ts: pd.Timestamp | datetime | None) -> datetime | None:
    if ts is None:
        return None
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize(IST)
    return t.tz_convert(UTC).to_pydatetime()


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=True
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def params_hash(params: dict) -> str:
    return hashlib.sha256(json.dumps(jsonable(params), sort_keys=True).encode()).hexdigest()


def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


class Journal:
    def __init__(self, url: str) -> None:
        _ensure_sqlite_dir(url)
        self.url = url
        self.engine: Engine = create_engine(url, future=True)
        m.metadata.create_all(self.engine)

    # ---- writes ------------------------------------------------------------------------
    def start_run(
        self,
        *,
        mode: str,
        data_split: str,
        period_start: date,
        period_end: date,
        config_hash: str,
        source: str,
        instances: list[str],
        notes: str = "",
    ) -> str:
        run_id = uuid.uuid4().hex
        with self.engine.begin() as cx:
            cx.execute(
                insert(m.runs).values(
                    run_id=run_id,
                    mode=mode,
                    data_split=data_split,
                    period_start=period_start,
                    period_end=period_end,
                    config_hash=config_hash,
                    git_sha=git_sha(),
                    source=source,
                    instances=instances,
                    started_at=datetime.now(UTC),
                    status="running",
                    notes=notes,
                )
            )
        return run_id

    def finish_run(self, run_id: str, *, status: str, n_signals: int, n_trades: int) -> None:
        with self.engine.begin() as cx:
            cx.execute(
                update(m.runs)
                .where(m.runs.c.run_id == run_id)
                .values(
                    status=status,
                    finished_at=datetime.now(UTC),
                    n_signals=n_signals,
                    n_trades=n_trades,
                )
            )

    def log_signals(self, rows: Iterable[dict]) -> None:
        rows = [
            {**r, "ts": to_utc(r["ts"]), "features": jsonable(r.get("features", {}))} for r in rows
        ]
        if rows:
            with self.engine.begin() as cx:
                cx.execute(insert(m.signals), rows)

    def log_trades(self, trades: Iterable[Trade]) -> None:
        rows = []
        for t in trades:
            rows.append(
                {
                    "trade_id": t.trade_id,
                    "run_id": t.run_id,
                    "signal_id": t.signal_id,
                    "instance_id": t.instance_id,
                    "strategy_id": t.strategy_id,
                    "strategy_version": t.strategy_version,
                    "timeframe": t.timeframe,
                    "symbol": t.symbol,
                    "side": str(t.side),
                    "qty": t.qty,
                    "signal_ts": to_utc(t.signal_ts),
                    "entry_ts": to_utc(t.entry_ts),
                    "entry_price": t.entry_price,
                    "exit_ts": to_utc(t.exit_ts),
                    "exit_price": t.exit_price,
                    "exit_reason": str(t.exit_reason),
                    "stop": t.stop,
                    "target": t.target,
                    "risk_per_unit": t.risk_per_unit,
                    "gross_pnl": t.gross_pnl,
                    "costs": t.costs,
                    "net_pnl": t.net_pnl,
                    "r_multiple": t.r_multiple,
                    "mfe_r": t.mfe_r,
                    "mae_r": t.mae_r,
                    "post_exit_mfe_r": t.post_exit_mfe_r,
                    "target_hit_after_stop": t.target_hit_after_stop,
                    "features": jsonable(t.features),
                    "context": jsonable(t.context),
                }
            )
        if rows:
            with self.engine.begin() as cx:
                cx.execute(insert(m.trades), rows)

    def log_day_context(self, run_id: str, rows: Iterable[tuple[date, str, dict]]) -> None:
        payload = [
            {"run_id": run_id, "day": d, "symbol": s, "tags": jsonable(tags)} for d, s, tags in rows
        ]
        if payload:
            with self.engine.begin() as cx:
                cx.execute(insert(m.day_context), payload)

    def log_trial(
        self,
        *,
        run_id: str,
        strategy_id: str,
        strategy_version: str,
        timeframe: str,
        params: dict,
        data_split: str,
        period_start: date,
        period_end: date,
        n_trades: int,
        expectancy_r: float | None,
    ) -> str:
        trial_id = uuid.uuid4().hex
        with self.engine.begin() as cx:
            cx.execute(
                insert(m.trials).values(
                    trial_id=trial_id,
                    created_at=datetime.now(UTC),
                    run_id=run_id,
                    strategy_id=strategy_id,
                    strategy_version=strategy_version,
                    timeframe=timeframe,
                    instance_id=f"{strategy_id}@{timeframe}",
                    params_hash=params_hash(params),
                    data_split=data_split,
                    period_start=period_start,
                    period_end=period_end,
                    n_trades=n_trades,
                    expectancy_r=jsonable(expectancy_r),
                )
            )
        return trial_id

    # ---- reads -------------------------------------------------------------------------
    def _frame(self, stmt: Any) -> pd.DataFrame:
        with self.engine.connect() as cx:
            df = pd.DataFrame(cx.execute(stmt).mappings().all())
        for col in TS_COLUMNS:
            if col in df.columns and len(df):
                ts = pd.to_datetime(df[col])
                ts = ts.dt.tz_localize(UTC) if ts.dt.tz is None else ts
                df[col] = ts.dt.tz_convert(IST)
        return df

    def read_runs(self, limit: int = 50) -> pd.DataFrame:
        return self._frame(select(m.runs).order_by(m.runs.c.started_at.desc()).limit(limit))

    def get_run(self, run_id: str) -> dict | None:
        with self.engine.connect() as cx:
            row = cx.execute(select(m.runs).where(m.runs.c.run_id == run_id)).mappings().first()
        return dict(row) if row else None

    def read_trades(self, run_id: str | None = None, instance_id: str | None = None) -> pd.DataFrame:
        stmt = select(m.trades)
        if run_id:
            stmt = stmt.where(m.trades.c.run_id == run_id)
        if instance_id:
            stmt = stmt.where(m.trades.c.instance_id == instance_id)
        return self._frame(stmt.order_by(m.trades.c.exit_ts, m.trades.c.trade_id))

    def read_signals(self, run_id: str) -> pd.DataFrame:
        stmt = select(m.signals).where(m.signals.c.run_id == run_id)
        return self._frame(stmt.order_by(m.signals.c.ts, m.signals.c.signal_id))

    def count_trials(self, strategy_id: str, data_split: str) -> int:
        stmt = (
            select(func.count())
            .select_from(m.trials)
            .where(m.trials.c.strategy_id == strategy_id, m.trials.c.data_split == data_split)
        )
        with self.engine.connect() as cx:
            return int(cx.execute(stmt).scalar_one())

    def ping(self) -> bool:
        with self.engine.connect() as cx:
            cx.execute(select(1))
        return True
