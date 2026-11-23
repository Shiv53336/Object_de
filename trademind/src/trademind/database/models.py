"""Journal schema (PLAN 8, BLUEPRINT 8). Portable across PostgreSQL and SQLite.

Timestamps are stored in UTC. Engine outputs (prices, P&L, R) are double precision; a
Decimal ledger for real orders and fills belongs to the live-execution phase.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

runs = Table(
    "runs",
    metadata,
    Column("run_id", String(64), primary_key=True),
    Column("mode", String(16), nullable=False),  # backtest | paper
    Column("data_split", String(16), nullable=False),  # research | holdout | live
    Column("period_start", Date, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("config_hash", String(64), nullable=False),
    Column("git_sha", String(64), nullable=False),
    Column("source", String(32), nullable=False),
    Column("instances", JSON, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    # running | done | failed; live paper also: stopped (Ctrl+C) | crashed | superseded
    Column("status", String(16), nullable=False),
    Column("n_signals", Integer),
    Column("n_trades", Integer),
    Column("notes", Text, nullable=False, default=""),
    # What was actually simulated, not just requested (revision 0002).
    Column("n_sessions", Integer),
    Column("first_session", Date),
    Column("last_session", Date),
)

signals = Table(
    "signals",
    metadata,
    Column("signal_id", String(64), primary_key=True),
    Column("run_id", String(64), ForeignKey("runs.run_id"), nullable=False),
    Column("instance_id", String(96), nullable=False),
    Column("strategy_id", String(64), nullable=False),
    Column("strategy_version", String(16), nullable=False),
    Column("timeframe", String(16), nullable=False),
    Column("symbol", String(64), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("side", String(8), nullable=False),
    Column("stop", Float, nullable=False),
    Column("target", Float),
    Column("ref_price", Float, nullable=False),
    Column("approved", Boolean, nullable=False),
    Column("reject_reason", String(32)),
    Column("qty", Integer, nullable=False),
    Column("reason", Text, nullable=False),
    Column("features", JSON, nullable=False),
    Index("ix_signals_run", "run_id", "instance_id"),
)

trades = Table(
    "trades",
    metadata,
    Column("trade_id", String(64), primary_key=True),
    Column("run_id", String(64), ForeignKey("runs.run_id"), nullable=False),
    Column("signal_id", String(64), nullable=False),
    Column("instance_id", String(96), nullable=False),
    Column("strategy_id", String(64), nullable=False),
    Column("strategy_version", String(16), nullable=False),
    Column("timeframe", String(16), nullable=False),
    Column("symbol", String(64), nullable=False),
    Column("side", String(8), nullable=False),
    Column("qty", Integer, nullable=False),
    Column("signal_ts", DateTime(timezone=True), nullable=False),
    Column("entry_ts", DateTime(timezone=True), nullable=False),
    Column("entry_price", Float, nullable=False),
    Column("exit_ts", DateTime(timezone=True), nullable=False),
    Column("exit_price", Float, nullable=False),
    Column("exit_reason", String(16), nullable=False),
    Column("stop", Float, nullable=False),
    Column("target", Float),
    Column("risk_per_unit", Float, nullable=False),
    Column("gross_pnl", Float, nullable=False),
    Column("costs", Float, nullable=False),
    Column("net_pnl", Float, nullable=False),
    Column("r_multiple", Float, nullable=False),
    Column("mfe_r", Float, nullable=False),
    Column("mae_r", Float, nullable=False),
    Column("post_exit_mfe_r", Float),
    Column("target_hit_after_stop", Boolean),
    Column("features", JSON, nullable=False),
    Column("context", JSON, nullable=False),
    Index("ix_trades_run", "run_id", "instance_id"),
)

day_context = Table(
    "day_context",
    metadata,
    Column("run_id", String(64), ForeignKey("runs.run_id"), primary_key=True),
    Column("day", Date, primary_key=True),
    Column("symbol", String(64), primary_key=True),
    Column("tags", JSON, nullable=False),
)

trials = Table(
    "trials",
    metadata,
    Column("trial_id", String(64), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("run_id", String(64), ForeignKey("runs.run_id"), nullable=False),
    Column("strategy_id", String(64), nullable=False),
    Column("strategy_version", String(16), nullable=False),
    Column("timeframe", String(16), nullable=False),
    Column("instance_id", String(96), nullable=False),
    Column("params_hash", String(64), nullable=False),
    Column("data_split", String(16), nullable=False),
    Column("period_start", Date, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("n_trades", Integer, nullable=False),
    Column("expectancy_r", Float),
    Index("ix_trials_strategy", "strategy_id", "data_split"),
)

llm_usage = Table(
    "llm_usage",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("model", String(128), nullable=False),
    Column("use_case", String(32), nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cost_usd", Float, nullable=False),
)

research_notes = Table(
    "research_notes",
    metadata,
    Column("note_id", String(64), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("kind", String(16), nullable=False),  # postmortem | weekly
    Column("period_start", Date, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("model", String(128), nullable=False),
    Column("content", JSON, nullable=False),
)

# Best bid/ask seen by the live feed, per symbol and minute (revision 0002): the first quote in the
# minute (fills at the bar open) and the last (signals at the bar close). Measures execution drift.
quotes = Table(
    "quotes",
    metadata,
    Column("run_id", String(64), ForeignKey("runs.run_id"), primary_key=True),
    Column("symbol", String(64), primary_key=True),
    Column("ts", DateTime(timezone=True), primary_key=True),
    Column("first_bid", Float),
    Column("first_ask", Float),
    Column("last_bid", Float),
    Column("last_ask", Float),
)
