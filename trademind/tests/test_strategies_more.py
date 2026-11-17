"""T01-T04: failed_orb_fade, overextension_fade, intraday_contraction, first_half_hour_momentum."""

from __future__ import annotations

from datetime import date, time

import numpy as np
import pandas as pd
import pytest

from trademind.database.journal import Journal
from trademind.services.backtesting.runner import run_backtest
from trademind.services.market_data.source import empty_bars
from trademind.services.market_data.synthetic import make_session
from trademind.services.strategy_engine.equity.failed_orb_fade import FailedOrbFade
from trademind.services.strategy_engine.equity.first_half_hour_momentum import FirstHalfHourMomentum
from trademind.services.strategy_engine.equity.intraday_contraction import IntradayContraction
from trademind.services.strategy_engine.equity.overextension_fade import OverextensionFade
from trademind.shared.config import AppConfig
from trademind.shared.enums import Side

from .helpers import DAY, INDEX, STOCK, frames_for, view_at

PREV = date(2025, 9, 1)


def _day(cfg: AppConfig, closes: list[float], *, prev: bool = True, total: int = 90,
         first_open: float | None = None, volumes: list[int] | None = None) -> pd.DataFrame:
    s = cfg.settings.session
    closes = closes + [closes[-1]] * (total - len(closes))
    vols = (volumes + [volumes[-1]] * (total - len(volumes))) if volumes else None
    today = make_session(DAY, closes, s, first_open=first_open or closes[0], volumes=vols)
    if not prev:
        return today
    return pd.concat([make_session(PREV, [1000.0] * 375, s), today], ignore_index=True)


def _view(cfg, bars, at, inst=INDEX, minutes=5):
    fr = frames_for(bars, inst, cfg, DAY, {minutes})
    return fr, view_at(fr, minutes, at)


# ---- T01 failed_orb_fade -------------------------------------------------------------------

UP_OR = list(np.linspace(997, 1002, 15))
BREAK_UP = [1002.6, 1003.0, 1003.5, 1004.0, 1004.2]
FAIL_UP = [1003.5, 1003.0, 1002.5, 1002.2, 1002.0]


def test_failed_orb_short(cfg: AppConfig) -> None:
    fr, view = _view(cfg, _day(cfg, UP_OR + BREAK_UP + FAIL_UP), "09:35")
    (sig,) = FailedOrbFade("5minute").on_bar(view)
    orng = fr.opening_range(15)
    assert sig.side == Side.SHORT
    assert sig.stop == pytest.approx(max(b["high"] for b in view.history[-2:]))
    assert sig.target == pytest.approx(orng.low)
    assert sig.features["reward_risk"] >= 1 and sig.features["minutes_since_breakout"] == 5


def test_failed_orb_long(cfg: AppConfig) -> None:
    or_path = list(np.linspace(1003, 998, 15))
    bars = _day(cfg, or_path + [997.4, 997, 996.5, 996, 995.8] + [996.5, 997, 997.5, 997.8, 998.0])
    fr, view = _view(cfg, bars, "09:35")
    (sig,) = FailedOrbFade("5minute").on_bar(view)
    assert sig.side == Side.LONG
    assert sig.stop == pytest.approx(min(b["low"] for b in view.history[-2:]))
    assert sig.target == pytest.approx(fr.opening_range(15).high)


def test_failed_orb_extreme_tracks_new_highs(cfg: AppConfig) -> None:
    higher = [1004.5, 1005, 1005.5, 1006, 1005.0]
    _, view = _view(cfg, _day(cfg, UP_OR + BREAK_UP + higher + FAIL_UP), "09:40")
    (sig,) = FailedOrbFade("5minute").on_bar(view)
    assert sig.stop == pytest.approx(max(b["high"] for b in view.history[-3:]))
    assert sig.stop > 1006


def test_failed_orb_too_late(cfg: AppConfig) -> None:
    hold = [1004.2] * 30
    _, view = _view(cfg, _day(cfg, UP_OR + BREAK_UP + hold + FAIL_UP), "10:05")
    assert view.bar["close"] < 1002.5
    assert FailedOrbFade("5minute").on_bar(view) == []


def test_failed_orb_only_first_event_counts(cfg: AppConfig) -> None:
    shallow = [1002.4] * 5  # back inside, but reward/risk too small: no signal
    path = UP_OR + BREAK_UP + shallow + [1002.4] * 15 + BREAK_UP + FAIL_UP
    _, v1 = _view(cfg, _day(cfg, path), "09:35")
    strat = FailedOrbFade("5minute", {"min_reward_risk": 5.0})
    assert strat.on_bar(v1) == []
    _, v2 = _view(cfg, _day(cfg, path), "10:05")
    assert FailedOrbFade("5minute").on_bar(v2) == []  # second breakout ignored, first is stale


@pytest.mark.parametrize("params", [{"min_reward_risk": 3.0}, {"max_risk_pct": 0.2}, {"bo_end": "09:30"}])
def test_failed_orb_negative_params(cfg: AppConfig, params) -> None:
    _, view = _view(cfg, _day(cfg, UP_OR + BREAK_UP + FAIL_UP), "09:35")
    assert FailedOrbFade("5minute", params).on_bar(view) == []


# ---- T02 overextension_fade ----------------------------------------------------------------

UP_SPIKE = [1000.0] * 40 + [1004, 1008, 1012, 1016, 1020] + [1022, 1024, 1025, 1026, 1026] + \
    [1025, 1023, 1021, 1019, 1018]
DOWN_SPIKE = [1000.0] * 40 + [996, 992, 988, 984, 980] + [978, 976, 975, 974, 974] + \
    [975, 977, 979, 981, 982]


def test_overextension_short(cfg: AppConfig) -> None:
    _, view = _view(cfg, _day(cfg, UP_SPIKE), "10:05")
    (sig,) = OverextensionFade("5minute").on_bar(view)
    assert sig.side == Side.SHORT
    assert sig.stop == pytest.approx(view.bar["day_high"])
    assert sig.target == pytest.approx(view.bar["vwap"])
    assert sig.features["z_extreme"] >= 3 and sig.features["reward_risk"] >= 1


def test_overextension_long(cfg: AppConfig) -> None:
    _, view = _view(cfg, _day(cfg, DOWN_SPIKE), "10:05")
    (sig,) = OverextensionFade("5minute").on_bar(view)
    assert sig.side == Side.LONG and sig.stop == pytest.approx(view.bar["day_low"])


def test_overextension_lookback(cfg: AppConfig) -> None:
    _, view = _view(cfg, _day(cfg, UP_SPIKE), "10:05")
    assert OverextensionFade("5minute", {"z_entry": 6.0, "z_lookback_bars": 1}).on_bar(view) == []
    assert len(OverextensionFade("5minute", {"z_entry": 6.0, "z_lookback_bars": 2}).on_bar(view)) == 1


def test_overextension_needs_reversal_window_and_atr(cfg: AppConfig) -> None:
    still_up = UP_SPIKE[:50] + [1027, 1028, 1029, 1030, 1031]
    _, view = _view(cfg, _day(cfg, still_up), "10:05")
    assert OverextensionFade("5minute").on_bar(view) == []
    _, view = _view(cfg, _day(cfg, UP_SPIKE), "10:05")
    assert OverextensionFade("5minute", {"window_start": "10:10"}).on_bar(view) == []
    _, view = _view(cfg, _day(cfg, UP_SPIKE, prev=False), "10:05")
    assert view.bar["atr14"] != view.bar["atr14"]  # NaN: only 11 bars today
    assert OverextensionFade("5minute").on_bar(view) == []


# ---- T03 intraday_contraction --------------------------------------------------------------

B1 = [1000, 1002, 1004, 1006, 1008, 1010, 1008, 1006, 1004, 1006,
      1008, 1010, 1008, 1006, 1004, 1006, 1008, 1006, 1005, 1005]
B2 = [1006, 1007, 1008, 1009, 1008, 1007, 1006, 1005, 1006, 1007,
      1008, 1009, 1008, 1007, 1006, 1007, 1008, 1008, 1008, 1008]
B3 = [1008.5, 1009, 1008.5, 1009] * 5
TRIGGER = [1011, 1012, 1013, 1014, 1015]


def _contraction(cfg, *, b3=B3, base_vol=500, trigger_vol=2000, history_days=12):
    s = cfg.settings.session
    days = pd.bdate_range(end=PREV, periods=history_days).date
    hist = [make_session(d, [1000.0] * 375, s, volumes=[1000] * 375) for d in days]
    closes = [float(x) for x in B1 + B2 + b3 + TRIGGER]
    vols = [base_vol] * 60 + [trigger_vol] * 5
    closes += [closes[-1]] * (90 - len(closes))
    vols += [1000] * (90 - len(vols))
    today = make_session(DAY, closes, s, volumes=vols)
    fr = frames_for(pd.concat(hist + [today], ignore_index=True), STOCK, cfg, DAY, {5})
    fr.ctx.in_play = True
    return fr, view_at(fr, 5, "10:15")


def test_contraction_long(cfg: AppConfig) -> None:
    _, view = _contraction(cfg)
    (sig,) = IntradayContraction("5minute").on_bar(view)
    f = sig.features
    assert sig.side == Side.LONG
    assert f["range_1"] > f["range_2"] > f["range_3"]
    assert f["base_rvol"] == pytest.approx(0.5) and f["trigger_rvol"] == pytest.approx(2.0)
    assert sig.stop == pytest.approx(min(b["low"] for b in view.history[-5:-1]))
    assert sig.target == pytest.approx(1015 + 2 * (1015 - sig.stop))


def test_contraction_negatives(cfg: AppConfig) -> None:
    fr, view = _contraction(cfg)
    fr.ctx.in_play = False
    assert IntradayContraction("5minute").on_bar(view) == []
    wide_b3 = [1004, 1010] * 10
    assert IntradayContraction("5minute").on_bar(_contraction(cfg, b3=wide_b3)[1]) == []
    assert IntradayContraction("5minute").on_bar(_contraction(cfg, base_vol=1000)[1]) == []
    assert IntradayContraction("5minute").on_bar(_contraction(cfg, trigger_vol=1000)[1]) == []
    assert IntradayContraction("5minute").on_bar(_contraction(cfg, history_days=5)[1]) == []


def test_contraction_needs_twelve_prior_bars(cfg: AppConfig) -> None:
    fr, _ = _contraction(cfg)
    view = view_at(fr, 5, "10:10")
    assert view.i == 11
    assert IntradayContraction("5minute", {"window_start": "09:30"}).on_bar(view) == []


# ---- T04 first_half_hour_momentum ----------------------------------------------------------


def _fhh(cfg, move: float, *, prev: bool = True) -> pd.DataFrame:
    path = list(np.linspace(1000, 1000 * (1 + move), 30))
    return _day(cfg, path, prev=prev, total=375, first_open=1000.0)


def test_fhh_long_and_short(cfg: AppConfig) -> None:
    _, view = _view(cfg, _fhh(cfg, 0.005), "14:55")
    (sig,) = FirstHalfHourMomentum("5minute").on_bar(view)
    assert sig.side == Side.LONG and sig.target is None
    assert sig.stop == pytest.approx(view.bar["close"] * 0.997)
    assert sig.features["r_open"] == pytest.approx(0.5, abs=0.01)
    _, view = _view(cfg, _fhh(cfg, -0.005), "14:55")
    (sig,) = FirstHalfHourMomentum("5minute").on_bar(view)
    assert sig.side == Side.SHORT and sig.stop == pytest.approx(view.bar["close"] * 1.003)


def test_fhh_negatives(cfg: AppConfig) -> None:
    _, view = _view(cfg, _fhh(cfg, 0.001), "14:55")
    assert FirstHalfHourMomentum("5minute").on_bar(view) == []
    _, view = _view(cfg, _fhh(cfg, 0.005), "14:50")
    assert FirstHalfHourMomentum("5minute").on_bar(view) == []
    _, view = _view(cfg, _fhh(cfg, 0.005, prev=False), "14:55")
    assert view.day.prev_close is None and FirstHalfHourMomentum("5minute").on_bar(view) == []


class _Src:
    def __init__(self, bars: dict[str, pd.DataFrame]) -> None:
        self.bars = bars

    def get_bars(self, symbol, interval, start, end):
        return self.bars.get(symbol, empty_bars()).copy()


def test_fhh_enters_late_and_squares_off(small_cfg: AppConfig, tmp_path) -> None:
    j = Journal(f"sqlite:///{tmp_path / 'j.sqlite'}")
    src = _Src({"NIFTY 50": _fhh(small_cfg, 0.005)})
    rid = run_backtest(small_cfg, src, DAY, DAY, j, strategies=[FirstHalfHourMomentum("5minute")])
    (t,) = j.read_trades(rid).to_dict("records")
    assert t["entry_ts"].time() == time(15, 0) and t["exit_ts"].time() == time(15, 20)
    assert t["exit_reason"] == "SQUAREOFF" and t["qty"] > 0 and t["qty"] % 75 == 0  # whole lots
