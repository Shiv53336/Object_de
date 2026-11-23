"""Backtest runner: load, prepare, run every session, journal, log trials."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, timedelta

import numpy as np

from trademind.database.journal import Journal, params_hash
from trademind.services.backtesting.dataset import SymbolData, prepare_symbol
from trademind.services.backtesting.session import EngineSession
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.learning.ledger import Hypothesis, ResearchLedger, ledger_dir
from trademind.services.market_data.source import DataSource
from trademind.services.paper_broker.broker import PaperBroker
from trademind.services.risk_engine.engine import RiskEngine
from trademind.services.strategy_engine.base import Strategy
from trademind.services.strategy_engine.registry import build_instances
from trademind.shared.config import AppConfig, config_hash
from trademind.shared.exceptions import ConfigError, DataError, HoldoutAccessError
from trademind.shared.models import Instrument

log = logging.getLogger(__name__)


SPLITS = ("research", "holdout", "forward", "replay")


def check_split(cfg: AppConfig, start: date, end: date, data_split: str) -> None:
    """research ends before the holdout; holdout stays inside its fixed window; forward and replay
    (live paper days) start after it ends (DECISIONS D29)."""
    v = cfg.settings.validation
    if start > end:
        raise ValueError("start must be on or before end")
    if data_split == "research":
        if end >= v.holdout_start:
            raise HoldoutAccessError(
                f"research runs must end before the holdout start {v.holdout_start}; "
                "use `trademind validate` for out-of-sample evaluation"
            )
    elif data_split == "holdout":
        if start < v.holdout_start or end > v.holdout_end:
            raise ValueError(f"holdout runs must lie within {v.holdout_start}..{v.holdout_end}")
    elif data_split in ("forward", "replay"):
        if start <= v.holdout_end:
            raise HoldoutAccessError(
                f"{data_split} runs must start after the holdout window ends ({v.holdout_end})"
            )
    else:
        raise ValueError(f"unknown data split {data_split!r}; expected one of {', '.join(SPLITS)}")


def run_backtest(
    cfg: AppConfig,
    source: DataSource,
    start: date,
    end: date,
    journal: Journal,
    *,
    data_split: str = "research",
    only: set[str] | None = None,
    strategies: list[Strategy] | None = None,
    source_name: str = "unknown",
    progress: Callable[[date, int, int], None] | None = None,
    instruments: dict[str, Instrument] | None = None,
) -> str:
    """Returns the run id. `strategies` overrides the configured instances (tests, research).
    `instruments` overrides config lot and tick sizes (a paper-day replay uses the live run's)."""
    check_split(cfg, start, end, data_split)
    instances = strategies if strategies is not None else build_instances(cfg.strategies, only)
    if not instances:
        raise ConfigError("no enabled strategy instances")
    s = cfg.settings
    instruments = instruments or build_instruments(s)
    timeframes = {x.minutes for x in instances}
    load_start = start - timedelta(days=s.backtest.warmup_days)

    data: dict[str, SymbolData] = {}
    for sym, inst in instruments.items():
        raw = source.get_bars(sym, s.session.base_interval, load_start, end)
        if raw.empty:
            log.warning("no bars", extra={"symbol": sym})
            continue
        data[sym] = prepare_symbol(inst, raw, cfg, timeframes)
    if s.market_symbol not in data:
        raise DataError(f"no data for market symbol {s.market_symbol}")
    sessions = [d for d in sorted(data[s.market_symbol].base_slices) if start <= d <= end]
    if not sessions:
        raise DataError("no sessions in the requested range")

    run_id = journal.start_run(
        mode="backtest",
        data_split=data_split,
        period_start=start,
        period_end=end,
        config_hash=config_hash(cfg.config_dir),
        source=source_name,
        instances=[x.instance_id for x in instances],
    )
    broker = PaperBroker(cfg.costs, s.session, run_id)
    engine = EngineSession(cfg, instances, broker, RiskEngine(s.risk), run_id)
    r_by_instance: dict[str, list[float]] = {x.instance_id: [] for x in instances}
    n_signals = n_trades = 0
    try:
        for k, day in enumerate(sessions):
            frames, opening, eod = {}, {}, {}
            for sym, sd in data.items():
                fr = sd.frames(day, cfg)
                if fr is None:
                    continue
                frames[sym], opening[sym], eod[sym] = fr, sd.opening(day), sd.eod_tags(day)
            res = engine.run_day(day, frames, opening, eod)
            journal.log_signals(res.signals)
            journal.log_trades(res.trades)
            journal.log_day_context(run_id, res.day_rows)
            n_signals += len(res.signals)
            n_trades += len(res.trades)
            for t in res.trades:
                r_by_instance[t.instance_id].append(t.r_multiple)
            if progress:
                progress(day, k + 1, len(sessions))
        ledger = ResearchLedger(ledger_dir(cfg))
        for x in instances:
            r = r_by_instance[x.instance_id]
            params = x.params.model_dump(mode="json")
            if data_split == "research":
                ledger.record_hypothesis(
                    Hypothesis(x.id, x.version, x.timeframe, params_hash(params)),
                    run_id=run_id, period_start=start, period_end=end, source=source_name,
                )
            journal.log_trial(
                run_id=run_id,
                strategy_id=x.id,
                strategy_version=x.version,
                timeframe=x.timeframe,
                params=params,
                data_split=data_split,
                period_start=start,
                period_end=end,
                n_trades=len(r),
                expectancy_r=float(np.mean(r)) if r else None,
            )
        journal.finish_run(run_id, status="done", n_signals=n_signals, n_trades=n_trades,
                           sessions=sessions)
    except Exception:
        journal.finish_run(run_id, status="failed", n_signals=n_signals, n_trades=n_trades)
        raise
    return run_id
