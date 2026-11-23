"""Live paper runner (T09): the backtest engine, fed minute by minute from live ticks.

Parity with the backtest is the design goal and is tested by replaying a recorded day.
Each completed minute g is processed once, `grace` seconds after it ends:
  * the bars for g are appended to today's data,
  * at timeframe closes (and the selection minute) features are rebuilt on a short window
    (the last `history_sessions` sessions plus today) while day context uses the full
    daily history, which gives the same values the backtest computes,
  * between closes only the raw bars are refreshed, since only the broker reads them,
  * EngineSession.step(g) runs exactly as in a backtest.
At the close the journal is written, today's bars go to the separate live store (never into the
research store), and a summary is sent.

Stream health: if no tick has arrived for `stall_seconds`, minutes are not processed on the clock
alone (they would be empty). Missing minutes are fetched as Kite candles when `fetch_minutes` is
given; after `give_up_minutes` without data the day carries on and the gap is recorded in the run.
Stalls, recoveries and crashes are sent as alerts. Best bid/ask from the feed is kept per minute
to measure execution drift against the fill model.
No order of any kind leaves this process: fills are simulated by PaperBroker.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from datetime import date, timedelta

import pandas as pd

from trademind.database.journal import Journal
from trademind.services.backtesting.dataset import SymbolData, prepare_symbol
from trademind.services.backtesting.session import DayResult, EngineSession
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.learning.metrics import scoreboard
from trademind.services.market_data.aggregate import BarAggregator
from trademind.services.market_data.resample import build_daily
from trademind.services.market_data.source import normalize_bars
from trademind.services.market_data.store import ParquetStore
from trademind.services.notify.telegram import Notifier
from trademind.services.paper_broker.broker import PaperBroker
from trademind.services.risk_engine.engine import RiskEngine
from trademind.services.strategy_engine.base import Strategy
from trademind.services.strategy_engine.view import DayFrames
from trademind.shared.clock import session_grid
from trademind.shared.config import AppConfig, config_hash
from trademind.shared.exceptions import DataError, HoldoutAccessError
from trademind.shared.models import Instrument

log = logging.getLogger(__name__)

# symbol, exchange time, last price, cumulative volume[, best bid, best ask]
Tick = tuple
FetchMinutes = Callable[[list[str], pd.Timestamp, pd.Timestamp], dict[str, pd.DataFrame]]


class QuoteBook:
    """First and last best bid/ask seen in each minute, per symbol."""

    def __init__(self, base: pd.Timedelta) -> None:
        self.base = base
        self.rows: dict[tuple[str, pd.Timestamp], dict] = {}

    def update(self, symbol: str, ts: pd.Timestamp, bid: float | None, ask: float | None) -> None:
        if bid is None or ask is None or bid <= 0 or ask <= 0:
            return
        minute = ts.floor(self.base)
        row = self.rows.get((symbol, minute))
        if row is None:
            self.rows[(symbol, minute)] = {"symbol": symbol, "ts": minute, "first_bid": bid, "first_ask": ask,
                                           "last_bid": bid, "last_ask": ask}
        else:
            row["last_bid"], row["last_ask"] = bid, ask


class LivePaperRunner:
    def __init__(
        self,
        cfg: AppConfig,
        store: ParquetStore,
        journal: Journal,
        instances: list[Strategy],
        day: date,
        *,
        notifier: Notifier | None = None,
        instruments: dict[str, Instrument] | None = None,
        history_sessions: int = 30,
        grace_seconds: float = 5.0,
        live_store: ParquetStore | None = None,
        fetch_minutes: FetchMinutes | None = None,
        stall_seconds: float = 30.0,
        give_up_minutes: float = 10.0,
    ) -> None:
        s = cfg.settings
        v = s.validation
        if v.holdout_start <= day <= v.holdout_end:
            raise HoldoutAccessError(f"{day} is inside the holdout window {v.holdout_start}.."
                                     f"{v.holdout_end}; live paper results there would leak into it")
        self.cfg, self.day, self.session = cfg, day, s.session
        self.interval = s.session.base_interval
        self.base_td = pd.Timedelta(minutes=s.session.base_minutes)
        self.grace = pd.Timedelta(seconds=grace_seconds)
        self.instruments = instruments or build_instruments(s)
        self.instances = instances
        self.tfs = {x.minutes for x in instances}
        self.store, self.journal, self.live_store = store, journal, live_store
        self.notifier = notifier or Notifier(token="", chat_id="")
        self.fetch_minutes = fetch_minutes
        self.stall = pd.Timedelta(seconds=stall_seconds)
        self.give_up = pd.Timedelta(minutes=give_up_minutes)

        load_start = day - timedelta(days=s.backtest.warmup_days)
        self._hist: dict[str, pd.DataFrame] = {}
        self._hist_daily: dict[str, pd.DataFrame] = {}
        for sym in self.instruments:
            hist = store.read(sym, self.interval, load_start, day - timedelta(days=1))
            if hist.empty:
                log.warning("no stored history, symbol skipped", extra={"symbol": sym})
                continue
            daily = build_daily(hist)
            first_kept = daily.index[-history_sessions:][0]
            self._hist[sym] = hist[(hist["ts"].dt.date >= first_kept).to_numpy()].reset_index(drop=True)
            self._hist_daily[sym] = daily
        if s.market_symbol not in self._hist:
            raise DataError(
                f"no stored history for {s.market_symbol}: run `trademind data download` first"
            )
        self._today: dict[str, list[dict]] = {sym: [] for sym in self._hist}
        self._ctx: dict = {}
        self._full: dict[str, SymbolData] = {}
        self._frames: dict[str, DayFrames] = {}
        self._dirty = True
        self.agg = BarAggregator(s.session)
        self.quotes = QuoteBook(self.base_td)

        earlier = journal.runs_on(day, "live")
        if not earlier.empty and (earlier["status"] == "done").any():
            done_id = earlier.loc[earlier["status"] == "done", "run_id"].iloc[-1]
            raise DataError(f"today's paper run {done_id} already finished; nothing to do")
        if not earlier.empty:
            journal.set_run_status(earlier["run_id"].tolist(), "superseded")

        self.run_id = journal.start_run(
            mode="paper",
            data_split="live",
            period_start=day,
            period_end=day,
            config_hash=config_hash(cfg.config_dir),
            source="kite-live",
            instances=[x.instance_id for x in instances],
        )
        self.broker = PaperBroker(cfg.costs, s.session, self.run_id)
        self.engine = EngineSession(cfg, instances, self.broker, RiskEngine(s.risk), self.run_id)
        self.engine.begin_day(day)
        self.stamps = session_grid(day, s.session.open, s.session.close, s.session.base_minutes)
        self.next_g = 0
        self.finished = False
        self.result: DayResult | None = None
        self._seen_positions: set = set()
        self._notified_trades = 0
        self._lock = threading.RLock()
        self.last_tick_ts: pd.Timestamp | None = None
        self.filled_through: pd.Timestamp | None = None
        self.stalled = False
        self.gave_up = False
        self._stall_since: pd.Timestamp | None = None
        self._last_fetch: pd.Timestamp | None = None
        self.filled_minutes = 0
        self.empty_minutes = 0
        self.stalls = 0

    # ---- inputs ------------------------------------------------------------------------
    def _add_bars(self, bars: Iterable[dict]) -> None:
        for b in bars:
            if b["symbol"] in self._today:
                self._today[b["symbol"]].append(b)
                self._dirty = True

    def backfill(self, bars: dict[str, pd.DataFrame], now: pd.Timestamp) -> int:
        """Today's already-completed minutes (from Kite candles) when starting late."""
        n = 0
        with self._lock:
            for sym, df in bars.items():
                if sym not in self._today or df.empty:
                    continue
                done = df[(df["ts"] + self.base_td <= now).to_numpy()]
                rows = done.assign(symbol=sym).to_dict("records")
                self._add_bars(rows)
                n += len(rows)
                if rows:
                    self.agg.seed(sym, int(done["volume"].sum()), done["ts"].iloc[-1])
                    self._mark_filled(done["ts"].iloc[-1] + self.base_td)
        return n

    def on_ticks(self, ticks: Iterable[Tick]) -> None:
        with self._lock:
            for sym, ts, price, cum, *quote in ticks:
                self._add_bars(self.agg.on_tick(sym, ts, price, cum))
                if self.last_tick_ts is None or ts > self.last_tick_ts:
                    self.last_tick_ts = ts
                if len(quote) == 2:
                    self.quotes.update(sym, ts, quote[0], quote[1])

    def _mark_filled(self, through: pd.Timestamp) -> None:
        if self.filled_through is None or through > self.filled_through:
            self.filled_through = through

    # ---- stream health -------------------------------------------------------------------
    def _data_through(self) -> pd.Timestamp:
        marks = [x for x in (self.last_tick_ts, self.filled_through) if x is not None]
        return max(marks) if marks else self.stamps[0]

    def _watch_stream(self, now: pd.Timestamp) -> None:
        ref = self._data_through()
        if now - ref <= self.stall or now <= self.stamps[0] + self.stall:
            if self.stalled:
                self.stalled, self.gave_up = False, False
                log.warning("tick stream recovered", extra={"filled": self.filled_minutes})
                self.notifier.send(f"TRADEMIND: market data back at {now:%H:%M:%S}; "
                                   f"{self.filled_minutes} minutes so far filled from Kite candles")
            return
        if not self.stalled:
            self.stalled, self._stall_since = True, ref
            self.stalls += 1
            log.warning("tick stream silent", extra={"since": str(ref)})
            self.notifier.error(f"no market data since {ref:%H:%M:%S}; paper run {self.run_id[:8]} is "
                                "waiting and filling missed minutes from Kite candles")
        retry = pd.Timedelta(seconds=20)
        if self.fetch_minutes and (self._last_fetch is None or now - self._last_fetch >= retry):
            self._last_fetch = now
            self._fill_gap(now)
        if not self.gave_up and self._stall_since is not None and now - self._stall_since > self.give_up:
            self.gave_up = True
            self.notifier.error(f"no market data for {self.give_up.total_seconds() / 60:.0f} minutes; "
                                "carrying on, missing minutes are recorded in the run")

    def _fill_gap(self, now: pd.Timestamp) -> None:
        if self.next_g >= len(self.stamps):
            return
        start = self.stamps[self.next_g]
        try:
            fetched = self.fetch_minutes(list(self._today), start, now) if self.fetch_minutes else {}
        except Exception as exc:  # a failed fetch is retried on the next poll
            log.warning("gap fill failed", extra={"error": str(exc)})
            return
        market = self.cfg.settings.market_symbol
        for sym, df in fetched.items():
            if sym not in self._today or df is None or df.empty:
                continue
            df = df[((df["ts"] >= start) & (df["ts"] + self.base_td <= now)).to_numpy()]
            if df.empty:
                continue
            new_ts = set(df["ts"])
            kept = [b for b in self._today[sym] if b["ts"] not in new_ts]
            removed = sum(int(b["volume"]) for b in self._today[sym] if b["ts"] in new_ts)
            self._today[sym] = kept + df.assign(symbol=sym).to_dict("records")
            self._today[sym].sort(key=lambda b: b["ts"])
            self._dirty = True
            self.agg.resume(sym, df["ts"].max(), int(df["volume"].sum()) - removed)
            if sym == market:
                self.filled_minutes += len(df)
                self._mark_filled(df["ts"].max() + self.base_td)

    # ---- the clock ---------------------------------------------------------------------
    def poll(self, now: pd.Timestamp) -> None:
        with self._lock:
            if self.finished:
                return
            self._add_bars(self.agg.flush(now - self.grace))
            self._watch_stream(now)
            n = len(self.stamps)
            while self.next_g < n:
                end = self.stamps[self.next_g] + self.base_td
                if end + self.grace > now:
                    break
                if self.stalled and not self.gave_up and end > self._data_through():
                    break  # wait for data instead of processing an empty minute
                self._process(self.next_g)
                self.next_g += 1
            if self.next_g >= len(self.stamps):
                self.finish()

    def _today_df(self, sym: str) -> pd.DataFrame:
        return normalize_bars(pd.DataFrame(self._today[sym]))

    def _frames_full(self) -> dict[str, DayFrames]:
        frames: dict[str, DayFrames] = {}
        for sym, rows in self._today.items():
            if not rows:
                continue
            today = self._today_df(sym)
            raw = pd.concat([self._hist[sym], today], ignore_index=True)
            daily = pd.concat([self._hist_daily[sym], build_daily(today)])
            sd = prepare_symbol(self.instruments[sym], raw, self.cfg, self.tfs, daily=daily)
            fr = sd.frames(self.day, self.cfg, ctx=self._ctx.get(sym))
            if fr is None:
                continue
            self._ctx[sym] = fr.ctx
            self._full[sym] = sd
            frames[sym] = fr
        self._frames = frames
        self._dirty = False
        return frames

    def _frames_light(self) -> dict[str, DayFrames]:
        """Fresh raw bars for the broker; timeframe frames unchanged (no timeframe closed)."""
        if not self._dirty:
            return self._frames
        frames: dict[str, DayFrames] = {}
        for sym, rows in self._today.items():
            if not rows:
                continue
            prev = self._frames.get(sym)
            if prev is None:
                return self._frames_full()
            today = self._today_df(sym)
            frames[sym] = DayFrames(sym, prev.instrument, prev.ctx, self.session, today, prev.tf)
        self._frames = frames
        self._dirty = False
        return frames

    def _process(self, g: int) -> None:
        market = self.cfg.settings.market_symbol
        if not any(b["ts"] == self.stamps[g] for b in self._today.get(market, [])[-3:]):
            self.empty_minutes += 1
        needs_full = g == self.engine.sel_g or g in self.engine.closes_at
        frames = self._frames_full() if needs_full else self._frames_light()
        opening = None
        if g == self.engine.sel_g:
            opening = {sym: sd.opening(self.day) for sym, sd in self._full.items()}
        self.engine.step(g, frames, opening)
        self._notify()

    def _notify(self) -> None:
        for key, pos in self.broker.positions.items():
            if (key, pos.entry_ts) not in self._seen_positions:
                self._seen_positions.add((key, pos.entry_ts))
                sig = pos.order.signal
                self.notifier.trade_opened(sig.instance_id, sig.symbol, str(sig.side), pos.order.qty,
                                           pos.entry_price, sig.stop, sig.target)
        trades = self.engine.closed_trades()
        for t in trades[self._notified_trades:]:
            self.notifier.trade_closed(t)
        self._notified_trades = len(trades)

    # ---- the close ---------------------------------------------------------------------
    def health_note(self) -> str:
        return (f"stalls={self.stalls} filled_minutes={self.filled_minutes} "
                f"empty_minutes={self.empty_minutes} late_ticks={self.agg.late_ticks}")

    def finish(self, status: str = "done") -> DayResult:
        """`done` at the close; `stopped` when ended early by hand; `crashed` after an error.
        Only `done` runs count as paper results (paper check, scoreboards, reviews)."""
        with self._lock:
            if self.finished and self.result is not None:
                return self.result
            frames = self._frames_full()
            eod = {sym: sd.eod_tags(self.day) for sym, sd in self._full.items()}
            res = self.engine.finish_day(frames, eod)
            self.journal.log_signals(res.signals)
            self.journal.log_trades(res.trades)
            self.journal.log_day_context(self.run_id, res.day_rows)
            self.journal.log_quotes(self.run_id, self.quotes.rows.values())
            self.journal.finish_run(
                self.run_id, status=status, n_signals=len(res.signals), n_trades=len(res.trades),
                sessions=[self.day], notes=self.health_note(),
            )
            if self.live_store is not None:
                for sym, rows in self._today.items():
                    if rows:
                        self.live_store.write(sym, self.interval, self._today_df(sym))
            self._notify()
            text = self.summary(res)
            if status != "done":
                text += f"\nRun ended early ({status}); it does not count as a paper day."
            self.notifier.daily_summary(text)
            self.result, self.finished = res, True
            return res

    def summary(self, res: DayResult) -> str:
        lines = [f"TRADEMIND paper {self.day}: {len(res.trades)} trades, {len(res.signals)} signals"]
        if res.trades:
            cols = ("instance_id", "net_pnl", "r_multiple", "gross_pnl", "costs", "mfe_r", "target",
                    "trade_id", "target_hit_after_stop")
            df = pd.DataFrame([{c: getattr(t, c) for c in cols} | {"exit_reason": str(t.exit_reason)}
                               for t in res.trades])
            board = scoreboard(df, self.cfg.settings.analytics.min_trades)
            for _, r in board.iterrows():
                lines.append(f"{r['instance_id']}: {int(r['n_trades'])} trades, "
                             f"{r['expectancy_r']:+.2f}R avg, Rs {r['total_net_pnl']:,.0f}")
        return "\n".join(lines)
