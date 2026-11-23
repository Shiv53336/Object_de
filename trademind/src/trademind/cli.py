"""TRADEMIND command line."""

from __future__ import annotations

import logging
import os
import time
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, NoReturn

import pandas as pd
import typer
import yaml

from trademind import __version__
from trademind.database.journal import Journal, migrate, params_hash
from trademind.services.ai_research.review import daily_postmortem, make_llm, telegram_text, weekly_review
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
from trademind.services.execution.paper_check import (
    OverlaySource,
    compare_bars,
    compare_trades,
    execution_drift,
    render,
    replay_day,
)
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.learning.ledger import (
    REAL_SOURCES,
    Hypothesis,
    LedgerError,
    ResearchLedger,
    ledger_dir,
)
from trademind.services.learning.metrics import scoreboard, to_markdown
from trademind.services.learning.validation import format_report, promotion_report, session_coverage
from trademind.services.market_data.adjust import AdjustedSource, overnight_jumps
from trademind.services.market_data.source import DataSource, validate_bars
from trademind.services.market_data.store import CsvSource, ParquetStore
from trademind.services.market_data.synthetic import SyntheticSource
from trademind.services.notify.telegram import TOKEN_RE, Notifier
from trademind.services.ops import preflight as pf
from trademind.services.strategy_engine.registry import available, build_instances
from trademind.shared.clock import IST, at
from trademind.shared.config import AppConfig, config_hash, load_config, runtime_paths
from trademind.shared.dotenv import load_env_file
from trademind.shared.exceptions import TrademindError
from trademind.shared.logging import setup_logging
from trademind.shared.power import keep_awake, on_battery

log = logging.getLogger(__name__)
app = typer.Typer(no_args_is_help=True, add_completion=False, help="TRADEMIND (paper trading only)")
data_app = typer.Typer(no_args_is_help=True, help="Market data tools")
paper_app = typer.Typer(no_args_is_help=True, help="Live paper trading (simulated fills only)")
db_app = typer.Typer(help="Journal database (T06)", no_args_is_help=True)
research_app = typer.Typer(no_args_is_help=True, help="AI research notes (advisory only)")
app.add_typer(data_app, name="data")
app.add_typer(paper_app, name="paper")
app.add_typer(db_app, name="db")
app.add_typer(research_app, name="research")

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


def _request_token(text: str) -> str:
    m = TOKEN_RE.search(text.strip())
    if not m:
        typer.echo("error: no request_token found in what you pasted", err=True)
        raise typer.Exit(2)
    return m.group(1) or m.group(2)


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
        return AdjustedSource(ParquetStore(runtime_paths().bars_dir), cfg.corporate_actions)
    if name == "csv":
        if csv_root is None:
            raise typer.BadParameter("--csv-root is required for --source csv")
        return AdjustedSource(CsvSource(csv_root), cfg.corporate_actions)
    if name == "kite":
        today = _now().date()
        _, _, gateway, directory = _kite(today)
        return AdjustedSource(KiteSource(gateway, directory), cfg.corporate_actions)
    raise typer.BadParameter(f"unknown source {name!r}")


@app.callback()
def _main(log_level: Annotated[str, typer.Option(help="Log level")] = "WARNING") -> None:
    load_env_file(Path(os.environ.get("TRADEMIND_ENV_FILE", ".env")))
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
    by: Annotated[str | None, typer.Option(help="Break down by a context tag, or year | quarter")] = None,
    split: Annotated[str, typer.Option(help="research (before the holdout) | forward (after)")] = "research",
    config_dir: ConfigDir = None,
) -> None:
    """Run a backtest and print the scoreboard. Holdout data is reachable only through `validate`."""
    if split not in ("research", "forward"):
        typer.echo("error: --split must be research or forward", err=True)
        raise typer.Exit(2)
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
            data_split=split,
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
    source: Annotated[str, typer.Option(help="Real data only: parquet | csv | kite")],
    start: Annotated[str | None, typer.Option(help="First holdout session (default: window start)")] = None,
    end: Annotated[str | None, typer.Option(help="Last holdout session (default: window end)")] = None,
    csv_root: Annotated[Path | None, typer.Option(help="Root folder for --source csv")] = None,
    config_dir: ConfigDir = None,
) -> None:
    """Out-of-sample check and promotion gate (PLAN 9.3, DECISIONS D29). The only command that
    reads holdout data. Every check that can refuse runs before any holdout data is read."""
    cfg = load_config(config_dir)
    v = cfg.settings.validation
    window = v.window
    first, last = (_date(start) if start else window[0]), (_date(end) if end else window[1])

    def refuse(msg: str) -> NoReturn:
        typer.echo(f"error: {msg}", err=True)
        raise typer.Exit(2)

    if source not in REAL_SOURCES:
        refuse("the holdout needs real market data: pass --source parquet (or csv, kite)")
    if first < window[0] or last > window[1] or first > last:
        refuse(f"holdout sessions must lie within the fixed window {window[0]}..{window[1]}")
    try:
        (strat,) = build_instances(cfg.strategies, {instance})
    except TrademindError as exc:
        refuse(str(exc))
    hyp = Hypothesis(strat.id, strat.version, strat.timeframe,
                     params_hash(strat.params.model_dump(mode="json")))
    ledger = ResearchLedger(ledger_dir(cfg))
    try:
        if ledger.uncommitted():
            refuse(f"the research ledger ({ledger.root}) has uncommitted changes; commit it first "
                   "so no holdout look can be lost: git add ledger && git commit -m ledger")
        looks = ledger.looks(strat.id, window)
        research_trials = ledger.distinct_hypotheses()
    except LedgerError as exc:
        refuse(str(exc))
    if len(looks) >= v.max_holdout_evals:
        refuse(f"{strat.id} has used its {v.max_holdout_evals} holdout looks for {window[0]}..{window[1]} "
               "(every version, timeframe and parameter set counts). Judge it on forward paper data "
               "instead (docs/CHARTER.md).")

    journal = Journal(runtime_paths().database_url)
    research = journal.find_research_run(instance, strat.version, hyp.params_hash,
                                         config_hash(cfg.config_dir), REAL_SOURCES)
    if research is None:
        refuse(f"no finished research backtest on real data for {instance} v{strat.version} with the "
               "current config and parameters. Run it first, e.g. `trademind backtest --source parquet "
               f"--start 2025-05-01 --end {window[0] - timedelta(days=1)} --instances {instance}`")
    covered = session_coverage(research["n_sessions"], research["period_start"], research["period_end"])
    if covered < v.min_session_coverage:
        refuse(f"research run {research['run_id']} simulated only {covered:.0%} of the weekdays in its "
               f"period (need {v.min_session_coverage:.0%}); download the missing data and rerun it")

    data = _source(cfg, source, 7, csv_root)
    market = cfg.settings.market_symbol
    bars = data.get_bars(market, cfg.settings.session.base_interval, first, last)
    days = sorted(set(bars["ts"].dt.date)) if not bars.empty else []
    if session_coverage(len(days), first, last) < v.min_session_coverage:
        refuse(f"only {len(days)} sessions of {market} data in {first}..{last}; download the holdout "
               "period first. No look was used.")

    try:
        holdout = run_backtest(cfg, data, first, last, journal, data_split="holdout", only={instance},
                               source_name=source)
    except (TrademindError, ValueError) as exc:
        refuse(f"{exc}. No look was recorded.")
    report = promotion_report(journal, v, instance, strat.version, research["run_id"], holdout,
                              research_trials=research_trials, holdout_evals=len(looks) + 1)
    ledger.record_look(hyp, window=window, period=(first, last), research_run_id=research["run_id"],
                       holdout_run_id=holdout, passed=report["passed"], source=source)
    typer.echo(format_report(report))
    typer.echo(f"\nHoldout look {len(looks) + 1} of {v.max_holdout_evals} for {strat.id} recorded in "
               f"{ledger.root}. Commit it now: git add ledger && git commit -m 'holdout look'")


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
def login(
    telegram: Annotated[bool, typer.Option(help="Send the login link on Telegram, wait for reply")] = False,
    timeout: Annotated[int, typer.Option(help="Seconds to wait for the Telegram reply")] = 1800,
) -> None:
    """Daily Kite login: open the URL, log in, paste the request_token from the redirect URL."""
    key, secret = _kite_env()
    if not secret:
        typer.echo("error: set KITE_API_SECRET in .env", err=True)
        raise typer.Exit(2)
    store = TokenStore(runtime_paths().data_dir / "kite_token.json")
    if store.load(_now().date()):
        typer.echo("Already logged in for today.")
        return
    gateway = KiteGateway(make_kite_client(key))
    if telegram:
        notifier = Notifier()
        if not notifier.enabled:
            typer.echo("error: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID for --telegram", err=True)
            raise typer.Exit(2)
        request_token = notifier.wait_for_request_token(gateway.login_url(), timeout_s=timeout)
        if not request_token:
            typer.echo("error: no login received", err=True)
            raise typer.Exit(3)
    else:
        url = gateway.login_url()
        typer.echo(f"1. Log in at: {url}")
        typer.echo("2. Paste the whole address you land on (it contains request_token=...).")
        webbrowser.open(url)
        request_token = _request_token(typer.prompt("redirect URL or request_token"))
    access = gateway.create_session(request_token, secret)
    store.save(access, _now().date())
    user = KiteGateway(make_kite_client(key, access)).profile().get("user_name", "?")
    typer.echo(f"Logged in as {user}. Session valid for today only.")
    if telegram:
        Notifier().send(f"TRADEMIND: logged in as {user}. Paper trading starts at 09:15.")


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
    """Write synthetic base bars into data/bars_synthetic (never into the research store)."""
    cfg = load_config(config_dir)
    s = cfg.settings
    src = SyntheticSource(seed, build_instruments(s), s.session, s.market_symbol)
    store = ParquetStore(runtime_paths().synthetic_bars_dir)
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
        dump = yaml.safe_dump({k: [d.isoformat() for d in v] for k, v in merged.items()})
        path.write_text(dump, encoding="utf-8")
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
    paths = runtime_paths()
    store = AdjustedSource(ParquetStore(paths.bars_dir), cfg.corporate_actions)
    journal = Journal(paths.database_url)
    notifier = Notifier()
    candles = KiteSource(gateway, directory)

    def fetch_minutes(symbols: list[str], start: pd.Timestamp, now: pd.Timestamp) -> dict:
        return {sym: candles.get_bars(sym, s.session.base_interval, today, today) for sym in symbols}

    try:
        runner = LivePaperRunner(cfg, store, journal, build_instances(cfg.strategies), today,
                                 notifier=notifier, instruments=instruments, grace_seconds=grace,
                                 live_store=ParquetStore(paths.live_bars_dir),
                                 fetch_minutes=fetch_minutes)
    except TrademindError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    syms = list(runner._today)
    now = _now()
    if now > at(today, s.session.open):
        bars = {sym: candles.get_bars(sym, s.session.base_interval, today, today) for sym in syms}
        n = runner.backfill(bars, now)
        typer.echo(f"backfilled {n} bars")
    stream = KiteTickStream(key, token, {directory.token(sym): sym for sym in syms}, runner.on_ticks, _now)
    stream.start()
    typer.echo(f"paper run {runner.run_id} started for {len(syms)} symbols; Ctrl+C to stop")
    if on_battery():
        typer.echo("warning: on battery power; plug the laptop in for the session", err=True)
    with keep_awake() as awake:
        if awake:
            typer.echo("Windows sleep is blocked until the run ends (the lid must stay open)")
        try:
            while not runner.finished:
                runner.poll(_now())
                time.sleep(1)
        except KeyboardInterrupt:
            typer.echo("stopping early: positions close at the last bar; the day will not count")
            runner.finish(status="stopped")
        except Exception as exc:
            notifier.error(f"paper run crashed: {type(exc).__name__}: {exc}. Restart `trademind paper run`; "
                           "it backfills the missed minutes.")
            try:
                runner.finish(status="crashed")
            except Exception:  # keep the original error
                log.exception("could not record the crashed run")
            raise
        finally:
            stream.stop()
    typer.echo(runner.summary(runner.result) if runner.result else "no result")


@app.command()
def preflight(
    purpose: Annotated[str, typer.Option("--for", help="paper | backtest")] = "paper",
    online: Annotated[bool, typer.Option(help="Also check the Kite session and clock online")] = True,
    config_dir: ConfigDir = None,
) -> None:
    """Readiness check for today: config, keys, Kite login, history, journal, disk, power, clock."""
    if purpose not in {"paper", "backtest"}:
        raise typer.BadParameter("--for must be paper or backtest")
    paths = runtime_paths()
    now = _now()
    checks = [pf.check_python()]
    try:
        cfg = load_config(config_dir)
    except Exception as exc:  # the config error message is the useful part
        checks.append(pf.Check("config", pf.FAIL, f"{type(exc).__name__}: {exc}"))
        text, code = pf.summarize(checks)
        typer.echo(text)
        raise typer.Exit(code) from exc
    checks.append(pf.check_config(cfg))
    checks += pf.check_env(os.environ, purpose)
    checks.append(pf.check_token(paths, now.date(), purpose))
    checks += pf.check_history(cfg, ParquetStore(paths.bars_dir), now.date(), purpose)
    checks.append(pf.check_journal(Journal(paths.database_url).ping))
    checks.append(pf.check_disk(paths.data_dir))
    if purpose == "paper":
        checks.append(pf.check_session_time(cfg, now))
        checks.append(pf.check_timezone(datetime.now().astimezone().utcoffset()))
        power = pf.check_power(on_battery())
        if power:
            checks.append(power)
    if online:
        checks += _online_checks(now)
    text, code = pf.summarize(checks)
    typer.echo(text)
    raise typer.Exit(code)


def _online_checks(now: pd.Timestamp) -> list[pf.Check]:
    import httpx

    out = []
    try:
        header = httpx.head("https://api.kite.trade", timeout=5).headers.get("date")
    except httpx.HTTPError:
        header = None
    out.append(pf.check_clock(header, _now()))
    key = os.environ.get("KITE_API_KEY", "")
    token = TokenStore(runtime_paths().data_dir / "kite_token.json").load(now.date())
    if key and token:
        try:
            user = KiteGateway(make_kite_client(key, token)).profile().get("user_name", "?")
            out.append(pf.Check("kite api", pf.OK, f"session works (user {user})"))
        except Exception as exc:  # any Kite error means today's session is unusable
            out.append(pf.Check("kite api", pf.FAIL, f"session rejected: {exc}; run `trademind login`"))
    return out


@paper_app.command("check")
def paper_check(
    day: Annotated[str | None, typer.Option(help="Paper day to check, YYYY-MM-DD (default: today)")] = None,
    kite: Annotated[bool, typer.Option(help="Fetch Kite candles to compare bars (needs a login)")] = True,
    config_dir: ConfigDir = None,
) -> None:
    """Compare a live paper day with backtest replays of the same day. Writes data/checks/DAY.md."""
    cfg = load_config(config_dir)
    s = cfg.settings
    d = _date(day) if day else _now().date()
    paths = runtime_paths()
    journal = Journal(paths.database_url)
    runs = journal.read_runs_between(d, d, "live")
    if runs.empty:
        typer.echo(f"error: no finished live paper run on {d}", err=True)
        raise typer.Exit(2)
    run = runs.iloc[-1]
    run_id, instance_ids = str(run["run_id"]), list(run["instances"] or [])
    live_trades = journal.read_trades(run_id)
    store = AdjustedSource(ParquetStore(paths.bars_dir), cfg.corporate_actions)
    live_store = ParquetStore(paths.live_bars_dir)
    notes: list[str] = []
    if run.get("notes"):
        notes.append(f"Stream health during the run: {run['notes']}")

    official: dict[str, pd.DataFrame] = {}
    instruments = None
    token = TokenStore(paths.data_dir / "kite_token.json").load(_now().date())
    if kite and token:
        _, _, gateway, directory = _kite(_now().date())
        instruments = _kite_instruments(cfg, directory, _now().date())
        src = KiteSource(gateway, directory)
        official = {sym: src.get_bars(sym, s.session.base_interval, d, d) for sym in build_instruments(s)}
    elif kite:
        notes.append("No Kite session today, so bars were not compared: run `trademind login` first.")
    if instruments is None:
        notes.append("Lot sizes come from config; if Kite's differ, quantities and P&L will differ too.")

    bar_diffs = []
    live_bars: dict[str, pd.DataFrame] = {}
    for sym, inst in (instruments or build_instruments(s)).items():
        live = live_store.read(sym, s.session.base_interval, d, d)
        if live.empty:
            continue
        live_bars[sym] = live
        if sym in official and not official[sym].empty:
            bar_diffs.append(compare_bars(sym, live, official[sym], inst.tick_size))
    if not live_bars:
        typer.echo(f"error: no live bars for {d} in {paths.live_bars_dir}", err=True)
        raise typer.Exit(2)

    try:
        on_live = compare_trades(live_trades, replay_day(cfg, OverlaySource(store, d, live_bars), d,
                                                         instance_ids, instruments))
        on_official = None
        if official:
            overlay = OverlaySource(store, d, {k: v for k, v in official.items() if not v.empty})
            on_official = compare_trades(live_trades, replay_day(cfg, overlay, d, instance_ids, instruments))
    except TrademindError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    drift = execution_drift(live_trades, journal.read_quotes(run_id))

    report = render(d, run_id, bar_diffs, on_live, on_official, notes, drift)
    (paths.data_dir / "checks").mkdir(parents=True, exist_ok=True)
    (paths.data_dir / "checks" / f"{d.isoformat()}.md").write_text(report, encoding="utf-8")
    typer.echo(report)
    typer.echo(f"saved: {paths.data_dir / 'checks' / (d.isoformat() + '.md')}")
    raise typer.Exit(0 if on_live.exact else 1)


@db_app.command("upgrade")
def db_upgrade() -> None:
    """Bring the journal schema to the latest revision (also done automatically on every start)."""
    from sqlalchemy import create_engine

    url = runtime_paths().database_url
    typer.echo(f"journal: {migrate(create_engine(url))}")


@research_app.command("postmortem")
def research_postmortem(
    run_id: Annotated[str | None, typer.Option(help="Run to review (default: latest live run)")] = None,
    config_dir: ConfigDir = None,
) -> None:
    """LLM review of one paper-trading day; writes data/reports and a Telegram summary."""
    cfg = load_config(config_dir)
    journal = Journal(runtime_paths().database_url)
    if run_id is None:
        runs = journal.read_runs(50)
        live = runs[(runs["data_split"] == "live") & (runs["status"] == "done")] if not runs.empty else runs
        if live.empty:
            typer.echo("error: no finished live paper run to review", err=True)
            raise typer.Exit(2)
        run_id = str(live.iloc[0]["run_id"])
    try:
        note = daily_postmortem(cfg, journal, make_llm(cfg, journal), run_id,
                                runtime_paths().data_dir / "reports")
    except (TrademindError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    text = telegram_text("TRADEMIND post-mortem", note)
    Notifier().send(text)
    typer.echo(text)


@research_app.command("weekly")
def research_weekly(
    start: Annotated[str | None, typer.Option(help="First day (default: 7 days ago)")] = None,
    end: Annotated[str | None, typer.Option(help="Last day (default: today)")] = None,
    config_dir: ConfigDir = None,
) -> None:
    """LLM review of the week; at most two proposals, written to data/research. Never applied."""
    cfg = load_config(config_dir)
    journal = Journal(runtime_paths().database_url)
    today = _now().date()
    a = _date(start) if start else today - pd.Timedelta(days=7).to_pytimedelta()
    b = _date(end) if end else today
    try:
        out = runtime_paths().data_dir / "research"
        note = weekly_review(cfg, journal, make_llm(cfg, journal), a, b, out)
    except (TrademindError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    text = telegram_text("TRADEMIND weekly review", note)
    Notifier().send(text)
    typer.echo(text)


@data_app.command("validate")
def data_validate(
    symbol: Annotated[str, typer.Option(help="Symbol, or 'all' for the universe")],
    start: Annotated[str, typer.Option()],
    end: Annotated[str, typer.Option()],
    source: Source = "parquet",
    seed: int = 7,
    csv_root: Annotated[Path | None, typer.Option()] = None,
    config_dir: ConfigDir = None,
) -> None:
    """Check stored bars against the bar contract. `--symbol all` checks the whole universe."""
    cfg = load_config(config_dir)
    s = cfg.settings
    src = _source(cfg, source, seed, csv_root)
    symbols = list(build_instruments(s)) if symbol == "all" else [symbol]
    failed = []
    for sym in symbols:
        df = src.get_bars(sym, s.session.base_interval, _date(start), _date(end))
        problems = validate_bars(df, s.session, s.session.base_minutes)
        if sym not in {i.symbol for i in s.universe.indices}:
            problems += [f"possible split or bonus on {d}: open / previous close = {r:.2f}. If it is one, "
                         "add it to config/corporate_actions.yaml" for d, r in overnight_jumps(df)]
        typer.echo(f"{sym}: {len(df)} bars")
        typer.echo("  " + "\n  ".join(problems) if problems else "  OK")
        if df.empty or any(not p.startswith("info:") for p in problems):
            failed.append(sym)
    if len(symbols) > 1:
        typer.echo(f"\n{len(symbols) - len(failed)} of {len(symbols)} symbols clean"
                   + (f"; check: {', '.join(failed)}" if failed else ""))
    if failed:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
