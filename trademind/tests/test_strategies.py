from __future__ import annotations

from datetime import date, time

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from trademind.services.market_data.synthetic import make_bars, make_session
from trademind.services.strategy_engine.equity.orb_momentum import OrbMomentum
from trademind.services.strategy_engine.equity.sweep_reversal import SweepReversal
from trademind.services.strategy_engine.registry import available, build_instances
from trademind.shared.config import AppConfig, StrategiesConfig
from trademind.shared.enums import Side
from trademind.shared.exceptions import ConfigError

from .helpers import DAY, INDEX, STOCK, frames_for, view_at

PREV = date(2025, 9, 1)

# ---- registry ------------------------------------------------------------------------------


def test_registry_builds_enabled_instances(cfg: AppConfig) -> None:
    assert {"orb_momentum", "sweep_reversal"} <= set(available())
    ids = [s.instance_id for s in build_instances(cfg.strategies)]
    assert ids == sorted(ids) and "orb_momentum@15minute" in ids
    assert not any(i.startswith("failed_orb_fade") for i in ids)  # disabled, not implemented


def test_registry_rejects_enabled_unknown_and_bad_filter(cfg: AppConfig) -> None:
    bad = StrategiesConfig.model_validate({"instances": [{"id": "nope", "timeframe": "5minute"}]})
    with pytest.raises(ConfigError, match="not implemented"):
        build_instances(bad)
    with pytest.raises(ConfigError, match="unknown or disabled"):
        build_instances(cfg.strategies, only={"failed_orb_fade@5minute"})


def test_params_validated() -> None:
    with pytest.raises(ValidationError):
        OrbMomentum("5minute", {"bogus": 1})
    assert OrbMomentum("5minute", {"entry_end": "10:30"}).params.entry_end == time(10, 30)


# ---- orb_momentum --------------------------------------------------------------------------


def _orb_day(cfg: AppConfig, or_path, after, *, minutes_total: int = 60) -> pd.DataFrame:
    closes = list(or_path) + list(after)
    closes += [closes[-1]] * (minutes_total - len(closes))
    return make_session(DAY, closes, cfg.settings.session, first_open=or_path[0])


UP_OR = np.linspace(1000, 1003.5, 15)
DOWN_OR = np.linspace(1000, 996.5, 15)


def _orb(cfg, bars, inst=INDEX, at="09:30", **params):
    fr = frames_for(bars, inst, cfg, DAY, {5})
    return OrbMomentum("5minute", params), fr, view_at(fr, 5, at)


def test_orb_long(cfg: AppConfig) -> None:
    strat, fr, view = _orb(cfg, _orb_day(cfg, UP_OR, [1003.8, 1004.5, 1005, 1005.5, 1006]))
    (sig,) = strat.on_bar(view)
    orng = fr.opening_range(15)
    assert sig.side == Side.LONG and sig.ts == view.now
    assert sig.stop == pytest.approx(orng.low) == pytest.approx(999.5)
    assert sig.target == pytest.approx(1006 + 2 * (1006 - orng.low))
    assert {"risk_pct", "vwap", "or_high", "trend_15m", "market_above_vwap"} <= set(sig.features)
    assert strat.on_bar(view) == []  # one signal per symbol per session
    strat.on_day_start(DAY)
    assert len(strat.on_bar(view)) == 1


def test_orb_short(cfg: AppConfig) -> None:
    strat, fr, view = _orb(cfg, _orb_day(cfg, DOWN_OR, [996.2, 995.5, 995, 994.5, 994]))
    (sig,) = strat.on_bar(view)
    assert sig.side == Side.SHORT
    assert sig.stop == pytest.approx(fr.opening_range(15).high)
    assert sig.target < 994


@pytest.mark.parametrize(
    "or_path,after,at,params",
    [
        (UP_OR, [1003.6, 1003.7, 1003.8, 1003.9, 1003.9], "09:30", {}),  # still inside the range
        (UP_OR[::-1], [1003.8, 1004.5, 1005, 1005.5, 1006], "09:30", {}),  # opening went down
        (UP_OR, [1006] * 5 + [1002] * 5 + [1007] * 5, "09:40", {}),  # not the first close above
        (UP_OR, [1003.8, 1004.5, 1005, 1005.5, 1006], "09:30", {"entry_end": "09:30"}),
        (UP_OR, [1003.8, 1004.5, 1005, 1005.5, 1006], "09:30", {"max_risk_pct": 0.5}),
        (UP_OR, [1003.8, 1004.5, 1005, 1005.5, 1006], "09:25", {}),  # before the range ends
    ],
)
def test_orb_negative(cfg: AppConfig, or_path, after, at, params) -> None:
    strat, _, view = _orb(cfg, _orb_day(cfg, or_path, after), at=at, **params)
    assert strat.on_bar(view) == []


def test_orb_stock_needs_in_play(cfg: AppConfig) -> None:
    strat, fr, view = _orb(cfg, _orb_day(cfg, UP_OR, [1003.8, 1004.5, 1005, 1005.5, 1006]), inst=STOCK)
    assert strat.on_bar(view) == []
    fr.ctx.in_play, fr.ctx.or_rvol = True, 1.4
    assert strat.on_bar(view) == []
    fr.ctx.or_rvol = 2.0
    assert len(strat.on_bar(view)) == 1


def test_orb_stop_buffer_needs_atr(cfg: AppConfig) -> None:
    strat, _, view = _orb(cfg, _orb_day(cfg, UP_OR, [1003.8, 1004.5, 1005, 1005.5, 1006]),
                          stop_buffer_atr=0.5)
    assert strat.on_bar(view) == []  # two hours of data: atr14 is not available yet


# ---- sweep_reversal ------------------------------------------------------------------------

FLAT = (1000.0, 1000.2, 999.8, 1000.0, 1000)


def _sweep_bars(cfg: AppConfig, rows_after_open: list[tuple], *, pre: list[tuple] | None = None):
    s = cfg.settings.session
    prev = make_session(PREV, [1000.0] * 375, s)  # PDH 1000.5, PDL 999.5
    rows = (pre if pre is not None else [FLAT] * 15) + rows_after_open
    tail = rows[-1][3]
    rows += [(tail, tail + 0.1, tail - 0.1, tail, 1000)] * (60 - len(rows))
    return pd.concat([prev, make_bars(DAY, rows, s)], ignore_index=True)


SWEEP_UP = [
    (1000.0, 1003.0, 999.9, 1001.0, 1000),
    (1001.0, 1001.5, 1000.0, 1000.5, 1000),
    (1000.5, 1000.6, 999.6, 999.8, 1000),
    (999.8, 1000.0, 999.6, 999.7, 1000),
    (999.7, 999.9, 999.6, 999.7, 1000),
]


def _sweep(cfg, bars, at="09:30", **params):
    fr = frames_for(bars, INDEX, cfg, DAY, {5})
    return SweepReversal("5minute", params), fr, view_at(fr, 5, at)


def test_sweep_short(cfg: AppConfig) -> None:
    strat, fr, view = _sweep(cfg, _sweep_bars(cfg, SWEEP_UP))
    assert fr.ctx.prev_day_high == pytest.approx(1000.5)
    (sig,) = strat.on_bar(view)
    assert sig.side == Side.SHORT
    assert sig.stop == pytest.approx(1003.0)
    assert sig.target == pytest.approx(999.7 - 2 * (1003.0 - 999.7))
    assert sig.features["level_kind"] == "pdh"
    assert sig.features["sweep_pct"] == pytest.approx((1003 - 1000.5) / 1000.5 * 100)


def test_sweep_long(cfg: AppConfig) -> None:
    rows = [(1000.0, 1000.1, 997.0, 999.0, 1000), (999.0, 1000.0, 998.9, 999.9, 1000),
            (999.9, 1000.4, 999.6, 1000.2, 1000), (1000.2, 1000.4, 1000.0, 1000.3, 1000),
            (1000.3, 1000.4, 1000.1, 1000.3, 1000)]
    strat, _, view = _sweep(cfg, _sweep_bars(cfg, rows))
    (sig,) = strat.on_bar(view)
    assert sig.side == Side.LONG and sig.stop == pytest.approx(997.0)


def test_sweep_too_deep_is_a_breakout(cfg: AppConfig) -> None:
    rows = [(1000.0, 1010.0, 999.9, 1001.0, 1000)] + SWEEP_UP[1:]
    strat, _, view = _sweep(cfg, _sweep_bars(cfg, rows))
    assert strat.on_bar(view) == []


def test_sweep_not_reclaimed(cfg: AppConfig) -> None:
    rows = SWEEP_UP[:4] + [(1001.0, 1001.5, 1000.9, 1001.2, 1000)]
    strat, _, view = _sweep(cfg, _sweep_bars(cfg, rows))
    assert strat.on_bar(view) == []


def test_sweep_reclaim_too_late(cfg: AppConfig) -> None:
    hold = (1001.0, 1001.5, 1000.9, 1001.2, 1000)
    rows = [SWEEP_UP[0]] + [hold] * 19 + SWEEP_UP[2:]
    strat, _, view = _sweep(cfg, _sweep_bars(cfg, rows), at="09:50")
    assert view.bar["close"] < 1000.5
    assert strat.on_bar(view) == []


def test_sweep_before_window_does_not_count(cfg: AppConfig) -> None:
    pre = [FLAT] * 5 + [(1000.0, 1001.0, 999.9, 1000.0, 1000)] + [FLAT] * 9
    strat, _, view = _sweep(cfg, _sweep_bars(cfg, SWEEP_UP, pre=pre))
    assert strat.on_bar(view) == []


def test_sweep_opened_beyond_level(cfg: AppConfig) -> None:
    pre = [(1001.0, 1001.2, 1000.9, 1000.0, 1000)] + [FLAT] * 14
    strat, _, view = _sweep(cfg, _sweep_bars(cfg, SWEEP_UP, pre=pre))
    assert view.day.first_open > 1000.5
    assert strat.on_bar(view) == []
