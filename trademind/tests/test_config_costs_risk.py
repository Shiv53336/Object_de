from __future__ import annotations

import math
import shutil
from datetime import date
from pathlib import Path

import pytest

from trademind.services.paper_broker.costs import compute_costs, slippage_fraction
from trademind.services.risk_engine.engine import RiskEngine
from trademind.shared.config import AppConfig, config_hash, load_config
from trademind.shared.enums import RejectReason, Segment, Side
from trademind.shared.exceptions import ConfigError

from .conftest import CONFIG_DIR
from .helpers import INDEX, STOCK, signal

# ---- config ---------------------------------------------------------------------------


def _copy_config(tmp_path: Path) -> Path:
    dst = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, dst)
    return dst


def test_default_config_loads(cfg: AppConfig) -> None:
    s = cfg.settings
    assert s.session.base_minutes == 1
    assert s.session.length_minutes == 375
    assert s.market_symbol == "NIFTY 50"
    assert str(s.execution.mode) == "PAPER"


def test_unknown_key_rejected(tmp_path: Path) -> None:
    d = _copy_config(tmp_path)
    (d / "settings.yaml").write_text((d / "settings.yaml").read_text() + "\nsurprise: 1\n")
    with pytest.raises(Exception, match="surprise"):
        load_config(d)


def test_unquoted_time_rejected(tmp_path: Path) -> None:
    d = _copy_config(tmp_path)
    text = (d / "settings.yaml").read_text().replace('open: "09:15"', "open: 9:15")
    (d / "settings.yaml").write_text(text)
    with pytest.raises(Exception, match="quoted"):
        load_config(d)


def test_session_order_enforced(tmp_path: Path) -> None:
    d = _copy_config(tmp_path)
    text = (d / "settings.yaml").read_text().replace('squareoff_time: "15:20"', 'squareoff_time: "14:00"')
    (d / "settings.yaml").write_text(text)
    with pytest.raises(Exception, match="last_entry_time < squareoff_time"):
        load_config(d)


def test_only_paper_mode_accepted(tmp_path: Path) -> None:
    d = _copy_config(tmp_path)
    text = (d / "settings.yaml").read_text().replace("mode: PAPER", "mode: APPROVED_LIVE")
    (d / "settings.yaml").write_text(text)
    with pytest.raises(Exception, match="only PAPER"):
        load_config(d)


def test_timeframe_must_be_multiple_of_base(tmp_path: Path) -> None:
    d = _copy_config(tmp_path)
    text = (d / "settings.yaml").read_text().replace("base_interval: 1minute", "base_interval: 5minute")
    text = text.replace("or_minutes: 15", "or_minutes: 15")
    (d / "settings.yaml").write_text(text)
    (d / "strategies.yaml").write_text("instances:\n  - {id: orb_momentum, timeframe: 3minute}\n")
    with pytest.raises(ConfigError, match="multiple of the base"):
        load_config(d)


def test_config_hash_changes_with_content(tmp_path: Path) -> None:
    d = _copy_config(tmp_path)
    h1 = config_hash(d)
    assert h1 == config_hash(d)
    (d / "costs.yaml").write_text((d / "costs.yaml").read_text() + "\n")
    assert config_hash(d) != h1


def test_expiries_parsed(tmp_path: Path) -> None:
    d = _copy_config(tmp_path)
    (d / "expiries.yaml").write_text('"NIFTY 50": ["2025-09-30", "2025-09-02"]\n')
    assert load_config(d).expiries["NIFTY 50"] == [date(2025, 9, 2), date(2025, 9, 30)]


# ---- costs (PLAN 7 test vectors) ----------------------------------------------------------

VECTORS = [
    (Segment.EQ_INTRADAY, 100 * 1000, 100 * 1010, (40.0, 25.25, 6.1707, 0.2010, 3.0, 8.3469, 82.9686)),
    (Segment.EQ_INTRADAY, 10 * 500, 10 * 505, (3.0150, 1.2625, 0.3085, 0.0100, 0.15, 0.6000, 5.3461)),
    (Segment.FUT, 75 * 24000, 75 * 24050,
     (40.0, 901.875, 65.9486, 3.6037, 36.0, 19.7194, 1067.1468)),
    (Segment.OPT, 75 * 120, 75 * 150, (40.0, 16.875, 7.1948, 0.0203, 0.27, 8.4987, 72.8588)),
    (Segment.EQ_DELIVERY, 50 * 2000, 50 * 2200, (0.0, 210.0, 6.4470, 0.2100, 15.0, 1.1983, 232.8553)),
]


@pytest.mark.parametrize("segment,buy,sell,expected", VECTORS)
def test_cost_vectors(cfg: AppConfig, segment, buy, sell, expected) -> None:
    c = compute_costs(segment, buy, sell, cfg.costs)
    got = (c.brokerage, c.stt, c.txn, c.sebi, c.stamp, c.gst, c.total)
    for g, e in zip(got, expected, strict=True):
        assert g == pytest.approx(e, abs=5e-5)


def test_brokerage_cap_crossover(cfg: AppConfig) -> None:
    below = compute_costs(Segment.EQ_INTRADAY, 60_000, 0, cfg.costs).brokerage
    above = compute_costs(Segment.EQ_INTRADAY, 70_000, 0, cfg.costs).brokerage
    assert below == pytest.approx(18.0)
    assert above == pytest.approx(20.0)


def test_slippage_fraction(cfg: AppConfig) -> None:
    assert slippage_fraction(Segment.EQ_INTRADAY, cfg.costs) == pytest.approx(0.0003)


# ---- risk ----------------------------------------------------------------------------------


def _risk(cfg: AppConfig, **update) -> RiskEngine:
    r = RiskEngine(cfg.settings.risk.model_copy(update=update))
    r.start_day(date(2025, 9, 2))
    return r


def _eval(r: RiskEngine, sig, ref=100.0, inst=STOCK, open_=0, pending=0, has=False):
    return r.evaluate(sig, ref, inst, open_positions=open_, pending=pending, has_position_or_pending=has)


def test_sizing_stock(cfg: AppConfig) -> None:
    d = _eval(_risk(cfg), signal(stop=95.0))
    assert d.approved and d.qty == 200  # Rs 1000 / Rs 5 per share


def test_sizing_notional_cap(cfg: AppConfig) -> None:
    d = _eval(_risk(cfg), signal(stop=99.9, target=None))
    assert d.qty == 5000  # 10,000 by risk, capped by Rs 5 lakh / Rs 100


def test_sizing_index_lot_and_override(cfg: AppConfig) -> None:
    r = _risk(cfg)
    d = _eval(r, signal(stop=23950.0, target=None, symbol="NIFTY 50"), ref=24000.0, inst=INDEX)
    assert d.approved and d.qty == 75  # Rs 7500 / 50 pts = 150 -> 2 lots, notional cap -> 1 lot
    d2 = _eval(r, signal(stop=23800.0, target=None, symbol="NIFTY 50", at="10:05"),
               ref=24000.0, inst=INDEX)
    assert d2.reason == RejectReason.QTY_TOO_SMALL  # 7500 / 200 = 37 < one lot


@pytest.mark.parametrize(
    "sig,ref,reason",
    [
        (signal(stop=math.nan), 100.0, RejectReason.INVALID_INPUT),
        (signal(stop=101.0), 100.0, RejectReason.INVALID_INPUT),
        (signal(stop=95.0, target=99.0), 100.0, RejectReason.INVALID_INPUT),
        (signal(Side.SHORT, stop=99.0, target=90.0), 100.0, RejectReason.INVALID_INPUT),
        (signal(stop=100.0, target=None), 100.0, RejectReason.ZERO_RISK),
    ],
)
def test_invalid_inputs_fail_closed(cfg: AppConfig, sig, ref, reason) -> None:
    assert _eval(_risk(cfg), sig, ref=ref).reason == reason


def test_kill_switch(cfg: AppConfig) -> None:
    assert _eval(_risk(cfg, kill_switch=True), signal()).reason == RejectReason.KILL_SWITCH


def test_position_exists_and_max_open(cfg: AppConfig) -> None:
    r = _risk(cfg)
    assert _eval(r, signal(), has=True).reason == RejectReason.POSITION_EXISTS
    assert _eval(r, signal(), open_=1, pending=1).reason == RejectReason.MAX_OPEN_POSITIONS


def test_max_trades_per_day_and_reset(cfg: AppConfig) -> None:
    r = _risk(cfg)
    for _ in range(3):
        assert _eval(r, signal()).approved
    assert _eval(r, signal()).reason == RejectReason.MAX_TRADES_PER_DAY
    assert _eval(r, signal(strategy_id="other")).approved  # per instance
    r.start_day(date(2025, 9, 3))
    assert _eval(r, signal()).approved


class _T:
    def __init__(self, tid: str, r: float, instance_id: str = "probe@5minute") -> None:
        self.trade_id, self.r_multiple, self.net_pnl, self.instance_id = tid, r, r * 1000, instance_id


def test_consecutive_losses(cfg: AppConfig) -> None:
    r = _risk(cfg)
    r.on_trade_closed(_T("a", -1.0))
    r.on_trade_closed(_T("a", -1.0))  # duplicate ignored
    assert _eval(r, signal()).approved
    r.on_trade_closed(_T("b", -1.0))
    assert _eval(r, signal()).reason == RejectReason.CONSECUTIVE_LOSSES


def test_win_resets_consecutive_losses(cfg: AppConfig) -> None:
    r = _risk(cfg)
    for tid, rr in (("a", -1.0), ("b", 2.0), ("c", -1.0)):
        r.on_trade_closed(_T(tid, rr))
    assert _eval(r, signal()).approved


def test_daily_loss_limit(cfg: AppConfig) -> None:
    r = _risk(cfg)
    r.on_trade_closed(_T("a", -3.5))
    assert _eval(r, signal()).reason == RejectReason.DAILY_LOSS_LIMIT
