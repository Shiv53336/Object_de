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
from sqlalchemy import create_engine, func, insert, inspect, select, update
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
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, encoding="utf-8", timeout=5,
            check=True,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def params_hash(params: dict) -> str:
    return hashlib.sha256(json.dumps(jsonable(params), sort_keys=True).encode()).hexdigest()


def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


MIGRATIONS = Path(__file__).with_name("migrations")
BASELINE = "0001"  # the schema databases had before migrations existed (T06)


def _alembic_config(connection: Any) -> Any:
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.attributes["connection"] = connection
    return cfg


def migrate(engine: Engine) -> str:
    """Bring the schema to the latest revision (T06). Returns what was done.

    New database: create everything and mark it current. A database from before migrations
    existed: mark it as the baseline, then upgrade. Otherwise: upgrade (a no-op when current).
    """
    from alembic import command
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(_alembic_config(None)).get_current_head()
    with engine.begin() as cx:
        tables = set(inspect(cx).get_table_names())
        current = MigrationContext.configure(cx).get_current_revision()
        if current == head:
            return "current"
        cfg = _alembic_config(cx)
        if current is None and "runs" not in tables:
            m.metadata.create_all(cx)
            command.stamp(cfg, "head")
            return "created"
        if current is None:
            command.stamp(cfg, BASELINE)
        command.upgrade(cfg, "head")
        return "upgraded"


class Journal:
    def __init__(self, url: str) -> None:
        _ensure_sqlite_dir(url)
        self.url = url
        self.engine: Engine = create_engine(url, future=True)
        migrate(self.engine)

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

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        n_signals: int,
        n_trades: int,
        sessions: list[date] | None = None,
        notes: str | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": status, "finished_at": datetime.now(UTC),
                                  "n_signals": n_signals, "n_trades": n_trades}
        if sessions is not None:
            values |= {"n_sessions": len(sessions), "first_session": min(sessions, default=None),
                       "last_session": max(sessions, default=None)}
        if notes is not None:
            values["notes"] = notes
        with self.engine.begin() as cx:
            cx.execute(update(m.runs).where(m.runs.c.run_id == run_id).values(**values))

    def set_run_status(self, run_ids: Iterable[str], status: str) -> None:
        ids = list(run_ids)
        if ids:
            with self.engine.begin() as cx:
                cx.execute(update(m.runs).where(m.runs.c.run_id.in_(ids)).values(status=status))

    def log_quotes(self, run_id: str, rows: Iterable[dict]) -> None:
        rows = [{**r, "run_id": run_id, "ts": to_utc(r["ts"])} for r in rows]
        if rows:
            with self.engine.begin() as cx:
                cx.execute(insert(m.quotes), rows)

    def read_quotes(self, run_id: str) -> pd.DataFrame:
        return self._frame(select(m.quotes).where(m.quotes.c.run_id == run_id)
                           .order_by(m.quotes.c.symbol, m.quotes.c.ts))

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

    def find_research_run(self, instance_id: str, strategy_version: str, params_hash_: str,
                          config_hash_: str, sources: frozenset[str]) -> dict | None:
        """Latest finished research run on real data, with the current config, that tested this exact
        version and parameter set of the instance. None if there is none."""
        stmt = (
            select(m.runs)
            .where(m.runs.c.data_split == "research", m.runs.c.status == "done",
                   m.runs.c.config_hash == config_hash_, m.runs.c.source.in_(sorted(sources)))
            .order_by(m.runs.c.started_at.desc())
        )
        with self.engine.connect() as cx:
            for run in cx.execute(stmt).mappings():
                if instance_id not in (run["instances"] or []):
                    continue
                trial = cx.execute(
                    select(func.count()).select_from(m.trials).where(
                        m.trials.c.run_id == run["run_id"], m.trials.c.instance_id == instance_id,
                        m.trials.c.strategy_version == strategy_version,
                        m.trials.c.params_hash == params_hash_)
                ).scalar_one()
                if trial:
                    return dict(run)
        return None

    def latest_run(self, instance_id: str, data_split: str) -> str | None:
        """Most recent finished run of the given split that included the instance."""
        stmt = (
            select(m.runs.c.run_id, m.runs.c.instances)
            .where(m.runs.c.data_split == data_split, m.runs.c.status == "done")
            .order_by(m.runs.c.started_at.desc())
        )
        with self.engine.connect() as cx:
            for run_id, instances in cx.execute(stmt):
                if instance_id in (instances or []):
                    return run_id
        return None

    def log_llm_usage(self, model: str, use_case: str, input_tokens: int, output_tokens: int,
                      cost_usd: float) -> None:
        with self.engine.begin() as cx:
            cx.execute(insert(m.llm_usage).values(
                ts=datetime.now(UTC), model=model, use_case=use_case, input_tokens=input_tokens,
                output_tokens=output_tokens, cost_usd=cost_usd))

    def llm_cost_since(self, since: datetime) -> float:
        stmt = select(func.coalesce(func.sum(m.llm_usage.c.cost_usd), 0.0)).where(
            m.llm_usage.c.ts >= since.astimezone(UTC))
        with self.engine.connect() as cx:
            return float(cx.execute(stmt).scalar_one())

    def log_research_note(self, kind: str, period_start: date, period_end: date, model: str,
                          content: dict) -> str:
        note_id = uuid.uuid4().hex
        with self.engine.begin() as cx:
            cx.execute(insert(m.research_notes).values(
                note_id=note_id, created_at=datetime.now(UTC), kind=kind, period_start=period_start,
                period_end=period_end, model=model, content=jsonable(content)))
        return note_id

    def read_runs_between(self, start: date, end: date, data_split: str) -> pd.DataFrame:
        stmt = select(m.runs).where(
            m.runs.c.data_split == data_split, m.runs.c.status == "done",
            m.runs.c.period_start >= start, m.runs.c.period_end <= end)
        return self._frame(stmt.order_by(m.runs.c.period_start))

    def ping(self) -> bool:
        with self.engine.connect() as cx:
            cx.execute(select(1))
        return True
