"""Paper-vs-replay check for one live paper day (docs/TESTING.md, step 5).

Three comparisons, each answering a different question:

1. Bars. Live tick-built 1-minute bars against Kite's official candles: are we building bars right?
2. Replay on live bars. A backtest of the same day on the bars the live run saw. Live and backtest share
   EngineSession, so this must match exactly; any difference is an engine, timing or data-loading bug.
3. Replay on Kite candles. How much the day's result depends on tick-aggregation noise.
4. Execution drift. The fill model (next bar open plus fixed slippage) against the best bid/ask the
   live feed showed at that minute: what real fills would have cost beyond the model.

Replays run against a throwaway journal: they are never stored and never logged as trials, and they
only cover a day that already has a finished live run (DECISIONS D27).
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from trademind.database.journal import Journal
from trademind.services.backtesting.runner import run_backtest
from trademind.services.market_data.source import DataSource, normalize_bars
from trademind.services.strategy_engine.base import Strategy
from trademind.shared.config import AppConfig
from trademind.shared.models import Instrument

TRADE_KEY = ["instance_id", "symbol", "side", "entry_ts"]
COMPARED = ["qty", "entry_price", "exit_ts", "exit_price", "exit_reason", "net_pnl"]

# Bar-quality warning thresholds (per symbol, per day).
MAX_MISSING = 2
MAX_OHLC_SHARE = 0.05
MAX_VOLUME_DIFF_PCT = 2.0


@dataclass(frozen=True)
class BarDiff:
    symbol: str
    live_bars: int
    official_bars: int
    missing_live: int
    extra_live: int
    ohlc_mismatch: int
    max_close_diff_pct: float
    volume_diff_pct: float | None

    @property
    def ok(self) -> bool:
        common = max(1, min(self.live_bars, self.official_bars))
        vol_ok = self.volume_diff_pct is None or abs(self.volume_diff_pct) <= MAX_VOLUME_DIFF_PCT
        return (self.missing_live <= MAX_MISSING and self.ohlc_mismatch / common <= MAX_OHLC_SHARE
                and vol_ok)


def compare_bars(symbol: str, live: pd.DataFrame, official: pd.DataFrame, tick: float) -> BarDiff:
    """Minute-by-minute comparison; prices differing by less than half a tick count as equal."""
    lv, of = normalize_bars(live).set_index("ts"), normalize_bars(official).set_index("ts")
    common = lv.index.intersection(of.index)
    tol = tick / 2
    ohlc = ["open", "high", "low", "close"]
    diff = lv.loc[common, ohlc] - of.loc[common, ohlc]
    mismatch = int((diff.abs() > tol).any(axis=1).sum())
    close_pct = ((lv.loc[common, "close"] - of.loc[common, "close"]).abs() / of.loc[common, "close"] * 100)
    off_vol = float(of["volume"].sum())
    vol_pct = (float(lv["volume"].sum()) - off_vol) / off_vol * 100 if off_vol > 0 else None
    return BarDiff(
        symbol=symbol,
        live_bars=len(lv),
        official_bars=len(of),
        missing_live=len(of.index.difference(lv.index)),
        extra_live=len(lv.index.difference(of.index)),
        ohlc_mismatch=mismatch,
        max_close_diff_pct=float(close_pct.max()) if len(close_pct) else 0.0,
        volume_diff_pct=vol_pct,
    )


@dataclass
class TradeDiff:
    matched: int = 0
    changed: list[dict] = field(default_factory=list)
    only_live: list[dict] = field(default_factory=list)
    only_replay: list[dict] = field(default_factory=list)
    live_net: float = 0.0
    replay_net: float = 0.0

    @property
    def exact(self) -> bool:
        return not (self.changed or self.only_live or self.only_replay)


def _keyed(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=TRADE_KEY + COMPARED).set_index(TRADE_KEY)
    out = df.copy()
    for col in ("entry_ts", "exit_ts"):
        out[col] = pd.to_datetime(out[col], utc=True)
    out["side"] = out["side"].astype(str)
    out["exit_reason"] = out["exit_reason"].astype(str)
    return out.set_index(TRADE_KEY)[COMPARED]


def _row(key: tuple, values: dict | None = None) -> dict:
    out = dict(zip(TRADE_KEY, key, strict=True))
    out["entry_ts"] = pd.Timestamp(out["entry_ts"]).isoformat()
    return out | (values or {})


def compare_trades(live: pd.DataFrame, replay: pd.DataFrame, price_tol: float = 1e-6) -> TradeDiff:
    lv, rp = _keyed(live), _keyed(replay)
    out = TradeDiff(live_net=float(lv["net_pnl"].sum()) if len(lv) else 0.0,
                    replay_net=float(rp["net_pnl"].sum()) if len(rp) else 0.0)
    for key in lv.index.difference(rp.index):
        out.only_live.append(_row(key, {"net_pnl": float(lv.loc[key, "net_pnl"])}))
    for key in rp.index.difference(lv.index):
        out.only_replay.append(_row(key, {"net_pnl": float(rp.loc[key, "net_pnl"])}))
    for key in lv.index.intersection(rp.index):
        a, b = lv.loc[key], rp.loc[key]
        fields = {}
        for col in COMPARED:
            x, y = a[col], b[col]
            same = abs(float(x) - float(y)) <= price_tol if isinstance(x, (int, float)) else x == y
            if not same:
                fields[col] = (str(x), str(y))
        if fields:
            out.changed.append(_row(key, {"differences": fields}))
        else:
            out.matched += 1
    return out


@dataclass
class Drift:
    trades: int = 0
    with_quotes: int = 0
    mean_r: float = 0.0
    mean_bps: float = 0.0
    total_rupees: float = 0.0
    worst: list[dict] = field(default_factory=list)


def execution_drift(trades: pd.DataFrame, quotes: pd.DataFrame) -> Drift:
    """Cost of trading at the quoted bid/ask instead of the modelled fill, entry plus exit.
    Positive means real fills would have been worse than the model. Uses the first quote of the
    fill minute, so a fast stop-out can be worse still."""
    out = Drift(trades=len(trades))
    if trades.empty or quotes.empty:
        return out
    q = quotes.copy()
    q["ts"] = pd.to_datetime(q["ts"], utc=True)
    q = q.set_index(["symbol", "ts"])
    rows = []
    for _, t in trades.iterrows():
        sign = 1.0 if str(t["side"]) == "LONG" else -1.0
        entry_key = (t["symbol"], pd.Timestamp(t["entry_ts"]).tz_convert("UTC").floor("1min"))
        exit_key = (t["symbol"], pd.Timestamp(t["exit_ts"]).tz_convert("UTC").floor("1min"))
        if entry_key not in q.index or exit_key not in q.index:
            continue
        e, x = q.loc[entry_key], q.loc[exit_key]
        entry_quote = e["first_ask"] if sign > 0 else e["first_bid"]
        exit_quote = x["first_bid"] if sign > 0 else x["first_ask"]
        if pd.isna(entry_quote) or pd.isna(exit_quote):
            continue
        per_unit = sign * (entry_quote - t["entry_price"]) + sign * (t["exit_price"] - exit_quote)
        rows.append({"instance_id": t["instance_id"], "symbol": t["symbol"],
                     "entry_ts": pd.Timestamp(t["entry_ts"]).isoformat(),
                     "r": per_unit / t["risk_per_unit"] if t["risk_per_unit"] else 0.0,
                     "bps": per_unit / t["entry_price"] * 1e4, "rupees": per_unit * t["qty"]})
    if rows:
        df = pd.DataFrame(rows)
        out.with_quotes = len(df)
        out.mean_r, out.mean_bps = float(df["r"].mean()), float(df["bps"].mean())
        out.total_rupees = float(df["rupees"].sum())
        out.worst = df.sort_values("r", ascending=False).head(3).to_dict("records")
    return out


class OverlaySource:
    """Stored bars, with some symbols' rows for one day replaced (Kite candles for a live day)."""

    def __init__(self, base: DataSource, day: date, overrides: dict[str, pd.DataFrame]) -> None:
        self.base, self.day, self.overrides = base, day, overrides

    def get_bars(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        df = self.base.get_bars(symbol, interval, start, end)
        if symbol not in self.overrides or not start <= self.day <= end:
            return df
        keep = df[(df["ts"].dt.date != self.day).to_numpy()] if not df.empty else df
        return normalize_bars(pd.concat([keep, self.overrides[symbol]], ignore_index=True))


def replay_day(
    cfg: AppConfig,
    source: DataSource,
    day: date,
    instance_ids: list[str] | None = None,
    instruments: dict[str, Instrument] | None = None,
    strategies: list[Strategy] | None = None,
) -> pd.DataFrame:
    """Backtest one day into a throwaway journal and return its trades."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        journal = Journal(f"sqlite:///{(Path(tmp) / 'replay.sqlite').as_posix()}")
        try:
            run_id = run_backtest(cfg, source, day, day, journal, data_split="replay",
                                  only=set(instance_ids) if instance_ids else None,
                                  strategies=strategies, source_name="replay", instruments=instruments)
            return journal.read_trades(run_id)
        finally:
            journal.engine.dispose()


def _money(x: float) -> str:
    return f"Rs {x:,.0f}"


def render(day: date, run_id: str, bars: list[BarDiff], on_live: TradeDiff,
           on_official: TradeDiff | None, notes: list[str], drift: Drift | None = None) -> str:
    lines = [f"# Paper check {day} (live run {run_id})", ""]
    lines += ["## 1. Bars: live ticks vs Kite candles", ""]
    if bars:
        lines += ["| symbol | live | kite | missing | extra | OHLC diffs | max close diff | volume | ok |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for b in bars:
            vol = "n/a" if b.volume_diff_pct is None else f"{b.volume_diff_pct:+.1f}%"
            lines.append(f"| {b.symbol} | {b.live_bars} | {b.official_bars} | {b.missing_live} | "
                         f"{b.extra_live} | {b.ohlc_mismatch} | {b.max_close_diff_pct:.3f}% | {vol} | "
                         f"{'yes' if b.ok else 'CHECK'} |")
        bad = [b.symbol for b in bars if not b.ok]
        lines += ["", f"Verdict: {'OK' if not bad else 'CHECK ' + ', '.join(bad)} "
                      f"(warn above {MAX_MISSING} missing minutes, {MAX_OHLC_SHARE:.0%} of bars with OHLC "
                      f"diffs, or {MAX_VOLUME_DIFF_PCT}% volume difference)."]
    else:
        lines.append("Skipped: no Kite session, so no official candles to compare with.")
    lines += ["", "## 2. Replay on the live bars (must match exactly)", ""]
    lines += _trade_section(on_live)
    lines.append(f"Verdict: {'PASS' if on_live.exact else 'FAIL: live and replay disagree on the same bars'}")
    lines += ["", "## 3. Replay on Kite candles (sensitivity to bar building)", ""]
    if on_official is None:
        lines.append("Skipped: no Kite session.")
    else:
        lines += _trade_section(on_official)
        lines.append("Differences here are expected when bars differ; large P&L swings mean the strategies "
                     "are sensitive to small data differences.")
    lines += ["", "## 4. Execution drift (fill model vs quoted bid/ask)", ""]
    if drift is None or not drift.with_quotes:
        lines.append("No quotes recorded for this run's trades (the feed sends them in full mode).")
    else:
        lines.append(f"{drift.with_quotes} of {drift.trades} trades had quotes. Real fills at the quote "
                     f"would have cost {drift.mean_r:+.3f}R ({drift.mean_bps:+.1f} bps) per trade more "
                     f"than the model, {_money(drift.total_rupees)} in total. Positive means the model is "
                     "too kind.")
        for w in drift.worst:
            lines.append(f"- {w['instance_id']} {w['symbol']} {w['entry_ts']}: {w['r']:+.3f}R")
    if notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in notes]
    return "\n".join(lines) + "\n"


def _trade_section(d: TradeDiff) -> list[str]:
    total = d.matched + len(d.changed) + len(d.only_live)
    out = [f"Trades matched exactly: {d.matched} of {total} live. Net P&L live {_money(d.live_net)}, "
           f"replay {_money(d.replay_net)}.", ""]
    for r in d.changed:
        diffs = "; ".join(f"{k} {a} vs {b}" for k, (a, b) in r["differences"].items())
        out.append(f"- changed: {r['instance_id']} {r['symbol']} {r['side']} {r['entry_ts']}: {diffs}")
    for r in d.only_live:
        out.append(f"- only live: {r['instance_id']} {r['symbol']} {r['side']} {r['entry_ts']}")
    for r in d.only_replay:
        out.append(f"- only replay: {r['instance_id']} {r['symbol']} {r['side']} {r['entry_ts']}")
    if d.changed or d.only_live or d.only_replay:
        out.append("")
    return out
