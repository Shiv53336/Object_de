"""One trading session on the base-bar clock (PLAN 5.1). Shared by backtest and live paper."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from trademind.services.feature_engine.context import trade_tags
from trademind.services.feature_engine.selector import select_in_play
from trademind.services.paper_broker.broker import (
    Bar,
    BrokerEvent,
    EntryCancelled,
    PaperBroker,
    TradeClosed,
)
from trademind.services.risk_engine.engine import RiskEngine
from trademind.services.strategy_engine.base import Strategy
from trademind.services.strategy_engine.view import BarView, DayFrames
from trademind.shared.clock import minutes_between, session_grid
from trademind.shared.config import AppConfig
from trademind.shared.enums import ExitReason, Side
from trademind.shared.models import Order, Signal, Trade


@dataclass
class DayResult:
    signals: list[dict] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    day_rows: list[tuple[date, str, dict]] = field(default_factory=list)


@dataclass
class _Grid:
    has: np.ndarray
    o: np.ndarray
    h: np.ndarray
    lo: np.ndarray
    c: np.ndarray


class EngineSession:
    def __init__(
        self,
        cfg: AppConfig,
        instances: list[Strategy],
        broker: PaperBroker,
        risk: RiskEngine,
        run_id: str,
    ) -> None:
        self.cfg = cfg
        s = cfg.settings.session
        self.session = s
        self.b = s.base_minutes
        self.n = s.length_minutes // self.b
        self.instances = sorted(instances, key=lambda x: x.instance_id)
        self.by_id = {x.instance_id: x for x in self.instances}
        self.by_tf: dict[int, list[Strategy]] = {}
        for x in self.instances:
            self.by_tf.setdefault(x.minutes, []).append(x)
        self.broker = broker
        self.risk = risk
        self.run_id = run_id
        self.market_symbol = cfg.settings.market_symbol
        self.sel_g = cfg.settings.selector.or_minutes // self.b - 1
        self.sq_g = minutes_between(s.open, s.squareoff_time) // self.b
        self.closes_at: dict[int, list[int]] = {}
        for minutes in sorted(self.by_tf):
            step = minutes // self.b
            for k in range(s.length_minutes // minutes):
                self.closes_at.setdefault((k + 1) * step - 1, []).append(minutes)
        self._sig_seq = 0

    # ---- per-day setup -----------------------------------------------------------------
    def _grid(self, fr: DayFrames) -> _Grid:
        g = ((fr.base["ts"] - fr.open_ts) // pd.Timedelta(minutes=self.b)).to_numpy(dtype=np.int64)
        n = self.n
        arr = {k: np.full(n, np.nan) for k in ("o", "h", "lo", "c")}
        has = np.zeros(n, dtype=bool)
        ok = (g >= 0) & (g < n)
        g = g[ok]
        has[g] = True
        arr["o"][g] = fr.base["open"].to_numpy()[ok]
        arr["h"][g] = fr.base["high"].to_numpy()[ok]
        arr["lo"][g] = fr.base["low"].to_numpy()[ok]
        arr["c"][g] = fr.base["close"].to_numpy()[ok]
        return _Grid(has, **arr)

    def _tf_rows(self, fr: DayFrames) -> dict[int, dict[int, int]]:
        out: dict[int, dict[int, int]] = {}
        for minutes, df in fr.tf.items():
            if minutes not in self.by_tf or df.empty:
                out[minutes] = {}
                continue
            off = ((df["ts"] - fr.open_ts) // pd.Timedelta(minutes=1)).to_numpy(dtype=np.int64)
            close_g = (off + minutes) // self.b - 1
            out[minutes] = {int(gc): i for i, gc in enumerate(close_g)}
        return out

    # ---- the day -----------------------------------------------------------------------
    def run_day(self, day: date, frames: dict[str, DayFrames], opening: dict[str, dict],
                eod: dict[str, dict]) -> DayResult:
        res = DayResult()
        self.risk.start_day(day)
        for x in self.instances:
            x.on_day_start(day)
        self._records: dict[str, dict] = {}
        self._exit_g: dict[str, int] = {}
        grids = {sym: self._grid(fr) for sym, fr in frames.items()}
        tf_rows = {sym: self._tf_rows(fr) for sym, fr in frames.items()}
        stamps = session_grid(day, self.session.open, self.session.close, self.b)

        for g in range(self.n):
            for sym in self.broker.active_symbols():
                gr = grids.get(sym)
                if gr is not None and gr.has[g]:
                    bar = Bar(stamps[g], gr.o[g], gr.h[g], gr.lo[g], gr.c[g], g)
                    self._handle(self.broker.on_bar(sym, bar), res)
            if g == self.sel_g:
                self._select(frames, opening)
            for minutes in self.closes_at.get(g, ()):
                self._evaluate(minutes, g, frames, tf_rows)

        for sym in self.broker.active_symbols():
            gr = grids.get(sym)
            last = None
            if gr is not None and gr.has.any():
                k = int(np.flatnonzero(gr.has)[-1])
                last = Bar(stamps[k], gr.o[k], gr.h[k], gr.lo[k], gr.c[k], k)
            self._handle(self.broker.end_of_day(sym, last), res)

        for t in res.trades:
            fr = frames[t.symbol]
            if t.exit_reason == ExitReason.STOP:
                self._trap(t, grids[t.symbol])
            t.context = {
                **fr.ctx.tags,
                **eod.get(t.symbol, {}),
                **trade_tags(t.entry_ts, t.features, fr.instrument, t.timeframe),
            }
        res.signals = list(self._records.values())
        res.day_rows = [
            (day, sym, {**fr.ctx.tags, **eod.get(sym, {})}) for sym, fr in sorted(frames.items())
        ]
        return res

    def _handle(self, events: list[BrokerEvent], res: DayResult) -> None:
        for ev in events:
            if isinstance(ev, TradeClosed):
                self.risk.on_trade_closed(ev.trade)
                self._exit_g[ev.trade.trade_id] = ev.exit_g
                res.trades.append(ev.trade)
            elif isinstance(ev, EntryCancelled):
                rec = self._records[ev.order.signal_id]
                rec["approved"] = False
                rec["reject_reason"] = str(ev.reason)

    def _select(self, frames: dict[str, DayFrames], opening: dict[str, dict]) -> None:
        stocks = {
            sym: opening.get(sym, {}).get("or_rvol")
            for sym, fr in frames.items()
            if fr.instrument.kind == "stock"
        }
        chosen = select_in_play(
            stocks, self.cfg.settings.selector.top_n, self.cfg.settings.selector.min_or_rvol
        )
        for sym, fr in frames.items():
            op = opening.get(sym, {})
            fr.ctx.or_rvol = op.get("or_rvol")
            fr.ctx.in_play = fr.instrument.kind == "index" or sym in chosen
            fr.ctx.tags.update({k: v for k, v in op.items() if k != "or_rvol"})

    def _evaluate(self, minutes: int, g: int, frames: dict[str, DayFrames],
                  tf_rows: dict[str, dict[int, dict[int, int]]]) -> None:
        tf_name = f"{minutes}minute"
        market: BarView | None = None
        msym = self.market_symbol
        if msym in frames:
            r = tf_rows[msym].get(minutes, {}).get(g)
            if r is not None:
                market = BarView(frames[msym], minutes, tf_name, r, None)
                market.market = market
        views: dict[str, BarView] = {}
        signals: list[Signal] = []
        for sym in sorted(frames):
            r = tf_rows[sym].get(minutes, {}).get(g)
            if r is None:
                continue
            view = market if sym == msym and market is not None else BarView(
                frames[sym], minutes, tf_name, r, market
            )
            views[sym] = view
            for strat in self.by_tf[minutes]:
                if strat.in_scope(frames[sym].instrument):
                    signals.extend(strat.on_bar(view))
        signals.sort(key=lambda s: (s.instance_id, s.symbol))
        for sig in signals:
            self._decide(sig, views[sig.symbol])

    def _decide(self, sig: Signal, view: BarView) -> None:
        iid, sym = sig.instance_id, sig.symbol
        ref = float(view.bar["close"])
        dec = self.risk.evaluate(
            sig,
            ref,
            view.instrument,
            open_positions=self.broker.open_count(iid),
            pending=self.broker.pending_count(iid),
            has_position_or_pending=self.broker.has_position_or_pending(iid, sym),
        )
        self._sig_seq += 1
        sid = f"{self.run_id[:8]}-s{self._sig_seq:07d}"
        self._records[sid] = {
            "signal_id": sid,
            "run_id": self.run_id,
            "instance_id": iid,
            "strategy_id": sig.strategy_id,
            "strategy_version": sig.strategy_version,
            "timeframe": sig.timeframe,
            "symbol": sym,
            "ts": sig.ts,
            "side": str(sig.side),
            "stop": sig.stop,
            "target": sig.target,
            "ref_price": ref,
            "approved": dec.approved,
            "reject_reason": None if dec.reason is None else str(dec.reason),
            "qty": dec.qty,
            "reason": sig.reason,
            "features": sig.features,
        }
        if dec.approved:
            strat = self.by_id[iid]
            self.broker.queue_entry(
                Order(sid, sig, dec.qty, view.instrument, allow_late_entry=strat.allow_late_entry)
            )

    def _trap(self, t: Trade, gr: _Grid) -> None:
        """PLAN 9.5: what price did after a stop, up to the square-off bar."""
        g0 = self._exit_g.get(t.trade_id, -1) + 1
        window = slice(g0, self.sq_g)
        has = gr.has[window]
        if g0 >= self.sq_g or not has.any():
            return
        hi = float(np.nanmax(gr.h[window][has]))
        lo = float(np.nanmin(gr.lo[window][has]))
        if t.side == Side.LONG:
            t.post_exit_mfe_r = (hi - t.entry_price) / t.risk_per_unit
            t.target_hit_after_stop = None if t.target is None else hi >= t.target
        else:
            t.post_exit_mfe_r = (t.entry_price - lo) / t.risk_per_unit
            t.target_hit_after_stop = None if t.target is None else lo <= t.target
