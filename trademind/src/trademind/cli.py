"""TRADEMIND command line."""

from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer
import yaml

from trademind import __version__
from trademind.database.journal import Journal
from trademind.services.backtesting.runner import run_backtest
from trademind.services.broker_gateway.kite import (
    InstrumentDirectory,
    KiteGateway,
    KiteSource,
    TokenStore,
    make_kite_client,
)
from trademind.services.execution.kite_stream import KiteTickStream
from trademind.services.execution.live_paper import LivePaperRunner
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.learning.metrics import scoreboard, to_markdown
from trademind.services.learning.validation import format_report, promotion_report
from trademind.services.market_data.source import DataSource, validate_bars
from trademind.services.market_data.store import CsvSource, ParquetStore
from trademind.services.market_data.synthetic import SyntheticSource
from trademind.services.notify.telegram import Notifier
from trademind.services.strategy_engine.registry import available, build_instances
from trademind.shared.clock import IST, at
from trademind.shared.config import AppConfig, load_config, runtime_paths
from trademind.shared.exceptions import TrademindError
from trademind.shared.logging import setup_logging

app = typer.Typer(no_args_is_help=True, add_completion=False, help="TRADEMIND (paper trading only)")
data_app = typer.Typer(no_args_is_help=True, help="Market data tools")
paper_app = typer.Typer(no_args_is_help=True, help="Live paper trading (simulated fills only)")
app.add_typer(data_app, name="data")
app.add_typer(paper_app, name="paper")

ConfigDir = Annotated[Path | None, typer.Option(help="Config directory (default: ./config)")]
Source = Annotated[str, typer.Option(help="synthetic | parquet | csv | kite")]


def _date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise typer.BadParameter(f"expected YYYY-MM-DD, got {s!r}") from exc


def _now() -> pd.Timestamp:
    return pd.Timestamp.now(tz=IST)


def _kite_env() -> tuple[str, str]:
    key, secret = os.environ.get("KITE_API_KEY", ""), os.environ.get("KITE_API_SECRET", "")
    if not key:
        typer.echo("error: set KITE_API_KEY (and KITE_API_SECRET) in .env", err=True)
        raise typer.Exit(2)
    return key, secret


def _kite(today: date) -> tuple[str, str, KiteGateway, InstrumentDirectory]:
    key, _ = _kite_env()
    token = TokenStore(runtime_paths().data_dir / "kite_token.json").load(today)
    if not token:
        typer.echo("error: no Kite session for today: run `trademind login`", err=True)
        raise typer.Exit(2)
    gateway = KiteGateway(make_kite_client(key, token))
    directory = InstrumentDirectory.load_or_fetch(gateway, runtime_paths().data_dir, today)
    return key, token, gateway, directory


def _kite_instruments(cfg: AppConfig, directory: InstrumentDirectory, today: date) -> dict:
    overrides = {}
    for sym, inst in build_instruments(cfg.settings).items():
        found = directory.lot_and_tick(sym, inst.kind, today)
        if found:
            overrides[sym] = found
    return build_instruments(cfg.settings, overrides)


def _source(cfg: AppConfig, name: str, seed: int, csv_root: Path | None) -> DataSource:
    s = cfg.settings
    if name == "synthetic":
        return SyntheticSource(seed, build_instruments(s), s.session, s.market_symbol)
    if name == "parquet":
        return ParquetStore(runtime_paths().bars_dir)
    if name == "csv":
        if csv_root is None:
            raise typer.BadParameter("--csv-root is required for --source csv")
        return CsvSource(csv_root)
    if name == "kite":
        today = _now().date()
        _, _, gateway, directory = _kite(today)
        return KiteSource(gateway, directory)
    raise typer.BadParameter(f"unknown source {name!r}")


@app.callback()
def _main(log_level: Annotated[str, typer.Option(help="Log level")] = "WARNING") -> None:
    setup_logging(log_level, json_output=os.environ.get("TRADEMIND_LOG_JSON", "1") == "1")


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(__version__)


@app.command()
def strategies() -> None:
    """List implemented strategies and configured instances."""
    cfg = load_config()
    impl = set(available())
    typer.echo("implemented: " + ", ".join(sorted(impl)))
    for ic in cfg.strategies.instances:
        state = "enabled" if ic.enabled else "disabled"
        mark = "" if ic.id in impl else " (not implemented)"
        typer.echo(f"  {ic.instance_id:40s} {state}{mark}")


@app.command()
def backtest(
    start: Annotated[str, typer.Option(help="First session, YYYY-MM-DD")],
    end: Annotated[str, typer.Option(help="Last session, YYYY-MM-DD")],
    source: Source = "synthetic",
    seed: Annotated[int, typer.Option(help="Seed for synthetic data")] = 7,
    csv_root: Annotated[Path | None, typer.Option(help="Root folder for --source csv")] = None,
    instances: Annotated[str | None, typer.Option(help="Comma list, e.g. orb_momentum@5minute")] = None,
    by: Annotated[str | None, typer.Option(help="Also break the scoreboard down by a context tag")] = None,
    config_dir: ConfigDir = None,
) -> None:
    """Run a research backtest and print the scoreboard."""
    cfg = load_config(config_dir)
    only = {x.strip() for x in instances.split(",")} if instances else None
    journal = Journal(runtime_paths().database_url)

    def progress(day: date, k: int, n: int) -> None:
        if k % 20 == 0 or k == n:
            typer.echo(f"  {k}/{n} sessions ({day})", err=True)

    try:
        run_id = run_backtest(
            cfg,
            _source(cfg, source, seed, csv_root),
            _date(start),
            _date(end),
            journal,
            only=only,
            source_name=source,
            progress=progress,
        )
    except TrademindError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(f"run_id: {run_id}")
    trades = journal.read_trades(run_id)
    typer.echo(to_markdown(scoreboard(trades, cfg.settings.analytics.min_trades, by)))


@app.command()
def validate(
    instance: Annotated[str, typer.Option(help="Strategy instance, e.g. orb_momentum@5minute")],
    start: Annotated[str, typer.Option(help="First holdout session (>= validation.holdout_start)")],
    end: Annotated[str, typer.Option(help="Last holdout session")],
    source: Source = "synthetic",
    seed: Annotated[int, typer.Option(help="Seed for synthetic data")] = 7,
    csv_root: Annotated[Path | None, typer.Option(help="Root folder for --source csv")] = None,
    config_dir: ConfigDir = None,
) -> None:
    """Out-of-sample check and promotion gate (PLAN 9.3). The only command that reads holdout data."""
    cfg = load_config(config_dir)
    v = cfg.settings.validation
    journal = Journal(runtime_paths().database_url)
    try:
        (strat,) = build_instances(cfg.strategies, {instance})
    except TrademindError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    used = journal.count_holdout_evals(instance, strat.version)
    if used >= v.max_holdout_evals:
        typer.echo(f"error: {instance} v{strat.version} has used its {v.max_holdout_evals} holdout "
                   "evaluations. Change the strategy (new version) before looking again.", err=True)
        raise typer.Exit(2)
    research = journal.latest_run(instance, "research")
    if research is None:
        typer.echo(f"error: no finished research backtest includes {instance}; run `trademind backtest` "
                   "first", err=True)
        raise typer.Exit(2)
    try:
        holdout = run_backtest(cfg, _source(cfg, source, seed, csv_root), _date(start), _date(end), journal,
                               data_split="holdout", only={instance}, source_name=source)
    except (TrademindError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(format_report(promotion_report(journal, v, instance, strat.version, research, holdout)))


@app.command()
def report(
    run_id: Annotated[str, typer.Option(help="Run id from `backtest`")],
    by: Annotated[str | None, typer.Option(help="Context tag to break down by")] = None,
    config_dir: ConfigDir = None,
) -> None:
    """Scoreboard for a past run."""
    cfg = load_config(config_dir)
    journal = Journal(runtime_paths().database_url)
    if journal.get_run(run_id) is None:
        typer.echo(f"error: run {run_id} not found", err=True)
        raise typer.Exit(2)
    trades = journal.read_trades(run_id)
    typer.echo(to_markdown(scoreboard(trades, cfg.settings.analytics.min_trades, by)))


@app.command()
def runs(limit: int = 20) -> None:
    """List recent runs."""
    df = Journal(runtime_paths().database_url).read_runs(limit)
    if df.empty:
        typer.echo("no runs yet")
        return
    for _, r in df.iterrows():
        typer.echo(
            f"{r['run_id']}  {r['status']:7s} {r['data_split']:9s} "
            f"{r['period_start']}..{r['period_end']}  trades={r['n_trades']}"
        )


@app.command()
def login() -> None:
    """Daily Kite login: open the URL, log in, paste the request_token from the redirect URL."""
    key, secret = _kite_env()
    if not secret:
        typer.echo("error: set KITE_API_SECRET in .env", err=True)
        raise typer.Exit(2)
    gateway = KiteGateway(make_kite_client(key))
    typer.echo(f"1. Open: {gateway.login_url()}")
    typer.echo("2. After login, copy request_token=... from the redirect URL.")
    request_token = typer.prompt("request_token").strip()
    access = gateway.create_session(request_token, secret)
    TokenStore(runtime_paths().data_dir / "kite_token.json").save(access, _now().date())
    user = KiteGateway(make_kite_client(key, access)).profile().get("user_name", "?")
    typer.echo(f"Logged in as {user}. Session valid for today only.")


@app.command()
def api(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve the read-only API."""
    import uvicorn

    from trademind.api.main import create_app

    uvicorn.run(create_app(), host=host, port=port)


@data_app.command("synth")
def data_synth(
    start: Annotated[str, typer.Option()],
    end: Annotated[str, typer.Option()],
    seed: int = 7,
    config_dir: ConfigDir = None,
) -> None:
    """Write synthetic base bars for the universe into the Parquet store."""
    cfg = load_config(config_dir)
    s = cfg.settings
    src = SyntheticSource(seed, build_instruments(s), s.session, s.market_symbol)
    store = ParquetStore(runtime_paths().bars_dir)
    for sym in build_instruments(s):
        n = store.write(sym, s.session.base_interval, src.get_bars(sym, s.session.base_interval,
                                                                   _date(start), _date(end)))
        typer.echo(f"{sym}: {n} bars")


@data_app.command("download")
def data_download(
    start: Annotated[str, typer.Option(help="First date, YYYY-MM-DD")],
    end: Annotated[str, typer.Option(help="Last date, YYYY-MM-DD")],
    symbols: Annotated[str, typer.Option(help="Comma list, or 'all' for the universe")] = "all",
    config_dir: ConfigDir = None,
) -> None:
    """Download base-interval candles from Kite into the Parquet store (read-only API)."""
    cfg = load_config(config_dir)
    s = cfg.settings
    today = _now().date()
    _, _, gateway, directory = _kite(today)
    source = KiteSource(gateway, directory)
    store = ParquetStore(runtime_paths().bars_dir)
    wanted = list(build_instruments(s)) if symbols == "all" else [x.strip() for x in symbols.split(",")]
    for sym in wanted:
        df = source.get_bars(sym, s.session.base_interval, _date(start), _date(end))
        total = store.write(sym, s.session.base_interval, df) if not df.empty else 0
        found = validate_bars(df, s.session, s.session.base_minutes)
        problems = "; ".join(p for p in found if not p.startswith("info"))
        typer.echo(f"{sym}: +{len(df)} bars (store {total}){'  PROBLEMS: ' + problems if problems else ''}")


@data_app.command("instruments")
def data_instruments(
    write_expiries: Annotated[bool, typer.Option(help="Write upcoming expiries to expiries.yaml")] = False,
    config_dir: ConfigDir = None,
) -> None:
    """Refresh the Kite instruments dump; compare lot sizes with config."""
    cfg = load_config(config_dir)
    today = _now().date()
    _, _, _, directory = _kite(today)
    for sym, inst in build_instruments(cfg.settings).items():
        found = directory.lot_and_tick(sym, inst.kind, today)
        note = "" if not found or found[0] == inst.lot_size else "  <- differs from config"
        typer.echo(f"{sym:12s} token={directory.token(sym)} kite={found} config_lot={inst.lot_size}{note}")
    if write_expiries:
        exp = directory.expiries(today)
        merged = {k: sorted({*cfg.expiries.get(k, []), *v}) for k, v in exp.items()}
        path = cfg.config_dir / "expiries.yaml"
        path.write_text(yaml.safe_dump({k: [d.isoformat() for d in v] for k, v in merged.items()}))
        typer.echo(f"wrote {path}")


@paper_app.command("run")
def paper_run(
    grace: Annotated[float, typer.Option(help="Seconds to wait after each minute before processing")] = 5.0,
    config_dir: ConfigDir = None,
) -> None:
    """Live paper trading for today, from Kite ticks. Simulated fills only; no orders are sent."""
    cfg = load_config(config_dir)
    s = cfg.settings
    today = _now().date()
    key, token, gateway, directory = _kite(today)
    instruments = _kite_instruments(cfg, directory, today)
    store = ParquetStore(runtime_paths().bars_dir)
    journal = Journal(runtime_paths().database_url)
    notifier = Notifier()
    try:
        runner = LivePaperRunner(cfg, store, journal, build_instances(cfg.strategies), today,
                                 notifier=notifier, instruments=instruments, grace_seconds=grace)
    except TrademindError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    syms = list(runner._today)
    now = _now()
    if now > at(today, s.session.open):
        src = KiteSource(gateway, directory)
        bars = {sym: src.get_bars(sym, s.session.base_interval, today, today) for sym in syms}
        n = runner.backfill(bars, now)
        typer.echo(f"backfilled {n} bars")
    stream = KiteTickStream(key, token, {directory.token(sym): sym for sym in syms}, runner.on_ticks, _now)
    stream.start()
    typer.echo(f"paper run {runner.run_id} started for {len(syms)} symbols; Ctrl+C to stop")
    try:
        while not runner.finished:
            runner.poll(_now())
            time.sleep(1)
    except KeyboardInterrupt:
        typer.echo("stopping early: closing open paper positions at the last bar")
        runner.finish()
    finally:
        stream.stop()
    typer.echo(runner.summary(runner.result) if runner.result else "no result")


@data_app.command("validate")
def data_validate(
    symbol: Annotated[str, typer.Option()],
    start: Annotated[str, typer.Option()],
    end: Annotated[str, typer.Option()],
    source: Source = "parquet",
    seed: int = 7,
    csv_root: Annotated[Path | None, typer.Option()] = None,
    config_dir: ConfigDir = None,
) -> None:
    """Check stored bars against the bar contract."""
    cfg = load_config(config_dir)
    s = cfg.settings
    df = _source(cfg, source, seed, csv_root).get_bars(
        symbol, s.session.base_interval, _date(start), _date(end)
    )
    problems = validate_bars(df, s.session, s.session.base_minutes)
    typer.echo(f"{len(df)} bars")
    typer.echo("\n".join(problems) if problems else "OK")
    if any(not p.startswith("info:") for p in problems):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
