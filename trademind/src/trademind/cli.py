"""TRADEMIND command line."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from trademind import __version__
from trademind.database.journal import Journal
from trademind.services.backtesting.runner import run_backtest
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.learning.metrics import scoreboard, to_markdown
from trademind.services.market_data.source import DataSource, validate_bars
from trademind.services.market_data.store import CsvSource, ParquetStore
from trademind.services.market_data.synthetic import SyntheticSource
from trademind.services.strategy_engine.registry import available
from trademind.shared.config import AppConfig, load_config, runtime_paths
from trademind.shared.exceptions import TrademindError
from trademind.shared.logging import setup_logging

app = typer.Typer(no_args_is_help=True, add_completion=False, help="TRADEMIND (paper trading only)")
data_app = typer.Typer(no_args_is_help=True, help="Market data tools")
app.add_typer(data_app, name="data")

ConfigDir = Annotated[Path | None, typer.Option(help="Config directory (default: ./config)")]
Source = Annotated[str, typer.Option(help="synthetic | parquet | csv")]


def _date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise typer.BadParameter(f"expected YYYY-MM-DD, got {s!r}") from exc


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
