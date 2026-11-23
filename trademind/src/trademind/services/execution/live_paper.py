"""Live paper runner (T09): the backtest engine, fed minute by minute from live ticks.

Parity with the backtest is the design goal and is tested by replaying a recorded day.
Each completed minute g is processed once, `grace` seconds after it ends:
  * the bars for g are appended to today's data,
  * at timeframe closes (and the selection minute) features are rebuilt on a short window
    (the last `history_sessions` sessions plus today) while day context uses the full
    daily history, which gives the same values the backtest computes,
  * between closes only the raw bars are refreshed, since only the broker reads them,
  * EngineSession.step(g) runs exactly as in a backtest.
At the close the journal is written, today's bars are stored, and a summary is sent.
No order of any kind leaves this process: fills are simulated by PaperBroker.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable
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

Tick = tuple[str, pd.Timestamp, float, int | None]  # symbol, exchange time, last price, cum volume


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
        self.store, self.journal = store, journal
        self.notifier = notifier or Notifier(token="", chat_id="")

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
        return n

    def on_ticks(self, ticks: Iterable[Tick]) -> None:
        with self._lock:
            for sym, ts, price, cum in ticks:
                self._add_bars(self.agg.on_tick(sym, ts, price, cum))

    # ---- the clock ---------------------------------------------------------------------
    def poll(self, now: pd.Timestamp) -> None:
        with self._lock:
            if self.finished:
                return
            self._add_bars(self.agg.flush(now - self.grace))
            n = len(self.stamps)
            while self.next_g < n and self.stamps[self.next_g] + self.base_td + self.grace <= now:
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
    def finish(self) -> DayResult:
        with self._lock:
            if self.finished and self.result is not None:
                return self.result
            frames = self._frames_full()
            eod = {sym: sd.eod_tags(self.day) for sym, sd in self._full.items()}
            res = self.engine.finish_day(frames, eod)
            self.journal.log_signals(res.signals)
            self.journal.log_trades(res.trades)
            self.journal.log_day_context(self.run_id, res.day_rows)
            self.journal.finish_run(
                self.run_id, status="done", n_signals=len(res.signals), n_trades=len(res.trades)
            )
            for sym, rows in self._today.items():
                if rows:
                    self.store.write(sym, self.interval, self._today_df(sym))
            self._notify()
            self.notifier.daily_summary(self.summary(res))
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
