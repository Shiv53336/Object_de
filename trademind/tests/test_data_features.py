from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from trademind.services.feature_engine.context import build_day_table, opening_stats, time_bucket
from trademind.services.feature_engine.htf import add_htf_trend
from trademind.services.feature_engine.indicators import add_base_features, add_tf_features
from trademind.services.feature_engine.selector import select_in_play
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.market_data.resample import build_daily, resample_bars
from trademind.services.market_data.source import normalize_bars, validate_bars
from trademind.services.market_data.store import CsvSource, ParquetStore
from trademind.services.market_data.synthetic import SyntheticSource, make_bars
from trademind.shared.config import AppConfig

from .helpers import DAY, INDEX, STOCK

START, END = date(2025, 6, 2), date(2025, 7, 31)


@pytest.fixture(scope="module")
def synth(cfg: AppConfig) -> SyntheticSource:
    s = cfg.settings
    return SyntheticSource(7, build_instruments(s), s.session, s.market_symbol)


@pytest.fixture(scope="module")
def stock_bars(synth: SyntheticSource) -> pd.DataFrame:
    return synth.get_bars("RELIANCE", "1minute", START, END)


# ---- market data ---------------------------------------------------------------------------


def test_synthetic_is_deterministic_per_day(synth: SyntheticSource) -> None:
    d = date(2025, 6, 4)
    wide = synth.get_bars("RELIANCE", "1minute", date(2025, 6, 2), date(2025, 6, 6))
    one = synth.get_bars("RELIANCE", "1minute", d, d)
    pd.testing.assert_frame_equal(wide[wide["ts"].dt.date == d].reset_index(drop=True), one)


def test_synthetic_shape_and_contract(cfg: AppConfig, synth: SyntheticSource, stock_bars) -> None:
    assert (stock_bars.groupby(stock_bars["ts"].dt.date).size() == 375).all()
    assert [p for p in validate_bars(stock_bars, cfg.settings.session, 1) if not p.startswith("info")] == []
    idx = synth.get_bars("NIFTY 50", "1minute", START, START)
    assert (idx["volume"] == 0).all()


def test_validate_flags_problems(cfg: AppConfig, stock_bars) -> None:
    bad = stock_bars.head(10).copy()
    bad.loc[3, "high"] = bad.loc[3, "low"] - 1
    problems = validate_bars(bad, cfg.settings.session, 1)
    assert any("high below" in p for p in problems)
    assert any("missing" in p for p in problems)


def test_resample_5m_and_drop_incomplete_60m(cfg: AppConfig, stock_bars) -> None:
    s = cfg.settings.session
    day = stock_bars[stock_bars["ts"].dt.date == START]
    five = resample_bars(day, 5, s)
    assert len(five) == 75
    first = day.iloc[:5]
    assert five.iloc[0]["open"] == first["open"].iloc[0]
    assert five.iloc[0]["high"] == first["high"].max()
    assert five.iloc[0]["low"] == first["low"].min()
    assert five.iloc[0]["close"] == first["close"].iloc[-1]
    assert five.iloc[0]["volume"] == first["volume"].sum()
    sixty = resample_bars(day, 60, s)
    assert [t.strftime("%H:%M") for t in sixty["ts"]] == [
        "09:15", "10:15", "11:15", "12:15", "13:15", "14:15"
    ]


def test_parquet_store_roundtrip_and_merge(tmp_path, stock_bars) -> None:
    store = ParquetStore(tmp_path)
    part = stock_bars.head(500)
    assert store.write("RELIANCE", "1minute", part) == 500
    assert store.write("RELIANCE", "1minute", part) == 500  # idempotent
    changed = part.tail(10).assign(close=1.0)
    store.write("RELIANCE", "1minute", changed)
    back = store.read("RELIANCE", "1minute", START, END)
    assert len(back) == 500 and (back["close"].tail(10) == 1.0).all()
    assert str(back["ts"].dt.tz) == "Asia/Kolkata"
    assert store.read("NOPE", "1minute", START, END).empty


def test_csv_source(tmp_path, stock_bars) -> None:
    (tmp_path / "1minute").mkdir()
    out = stock_bars.head(375).copy()
    out["ts"] = out["ts"].dt.tz_localize(None)
    out.to_csv(tmp_path / "1minute" / "RELIANCE.csv", index=False)
    got = CsvSource(tmp_path).get_bars("RELIANCE", "1minute", START, START)
    pd.testing.assert_frame_equal(got, normalize_bars(stock_bars.head(375)))


# ---- features ------------------------------------------------------------------------------


def test_vwap_hand_example(cfg: AppConfig) -> None:
    rows = [(100, 102, 98, 100, 10), (100, 104, 100, 102, 30), (102, 103, 99, 101, 0)]
    b = make_bars(DAY, rows, cfg.settings.session)
    f = add_base_features(b, STOCK)
    assert f["vwap"].tolist() == pytest.approx([100.0, 101.5, 101.5])
    assert f["day_high"].tolist() == [102, 104, 104]
    idx = add_base_features(b, INDEX)
    assert idx["vwap"].tolist() == pytest.approx([100.0, 101.0, 101.0])


def test_atr_and_tod_rvol(cfg: AppConfig) -> None:
    s = cfg.settings.session
    frames = []
    days = pd.bdate_range("2025-06-02", periods=13).date
    for k, d in enumerate(days):
        vol = 2000 if k == 12 else 1000
        frames.append(make_bars(d, [(100, 101, 99, 100, vol)] * 15, s))
    tf = add_tf_features(resample_bars(pd.concat(frames, ignore_index=True), 5, s), STOCK)
    assert tf["atr14"].iloc[:13].isna().all() and tf["atr14"].iloc[13] == pytest.approx(2.0)
    last_day = tf[tf["ts"].dt.date == days[-1]]
    assert last_day["tod_rvol"].tolist() == pytest.approx([2.0, 2.0, 2.0])
    assert tf[tf["ts"].dt.date == days[9]]["tod_rvol"].isna().all()  # only 9 prior sessions


def _assert_prefix_equal(full: pd.DataFrame, part: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        a, b = full[c].iloc[: len(part)].reset_index(drop=True), part[c].reset_index(drop=True)
        pd.testing.assert_series_equal(a, b, check_names=False)


@pytest.mark.parametrize("cut", [1000, 5432, 9001])
def test_base_and_htf_features_are_causal(cfg: AppConfig, stock_bars, cut: int) -> None:
    s = cfg.settings.session
    full = add_htf_trend(add_base_features(stock_bars, STOCK), s)
    part = add_htf_trend(add_base_features(stock_bars.iloc[:cut], STOCK), s)
    _assert_prefix_equal(full, part, ["vwap", "day_high", "day_low", "trend_15m", "trend_60m"])


@pytest.mark.parametrize("cut", [200, 777, 1500])
def test_tf_features_are_causal(cfg: AppConfig, stock_bars, cut: int) -> None:
    tf = resample_bars(stock_bars, 5, cfg.settings.session)
    full = add_tf_features(tf, STOCK)
    part = add_tf_features(tf.iloc[:cut], STOCK)
    _assert_prefix_equal(full, part, ["atr14", "tod_rvol"])


def test_htf_trend_has_values(cfg: AppConfig, stock_bars) -> None:
    f = add_htf_trend(stock_bars, cfg.settings.session)
    assert set(f["trend_60m"].unique()) <= {"up", "down", "flat", "unknown"}
    assert f["trend_15m"].iloc[0] == "unknown" and (f["trend_15m"].iloc[-500:] != "unknown").all()


def test_day_table_and_opening_stats_are_causal(cfg: AppConfig, stock_bars) -> None:
    daily = build_daily(stock_bars)
    full = build_day_table(daily, STOCK, {})
    part = build_day_table(daily.iloc[:30], STOCK, {})
    pd.testing.assert_frame_equal(full.iloc[:30], part)
    s = cfg.settings.session
    o_full = opening_stats(stock_bars, STOCK, s, 15, daily.index)
    cut = stock_bars["ts"].dt.date < daily.index[30]
    o_part = opening_stats(stock_bars[cut.to_numpy()], STOCK, s, 15, daily.index[:30])
    pd.testing.assert_frame_equal(o_full.iloc[:30], o_part)


def test_day_table_values(cfg: AppConfig, stock_bars) -> None:
    daily = build_daily(stock_bars)
    t = build_day_table(daily, STOCK, {"STOCKS": [daily.index[3]]})
    assert np.isnan(t["prev_close"].iloc[0]) and t["gap_bucket"].iloc[0] == "unknown"
    assert t["prev_close"].iloc[5] == daily["close"].iloc[4]
    assert t["daily_atr_pct"].iloc[:15].isna().all() and t["daily_atr_pct"].iloc[15] > 0
    assert (t["daily_trend"].iloc[:30] == "unknown").all()
    assert t["is_expiry_day"].iloc[3] == "true" and t["is_expiry_day"].iloc[4] == "false"
    assert set(t["day_type"]) <= {"trend_up", "trend_down", "range", "mixed", "flat"}


def test_selector() -> None:
    rv = {"A": 3.0, "B": 2.0, "C": 2.0, "D": 1.4, "E": None, "F": float("nan"), "G": 1.5}
    assert select_in_play(rv, top_n=3, min_or_rvol=1.5) == {"A", "B", "C"}
    assert select_in_play(rv, top_n=10, min_or_rvol=1.5) == {"A", "B", "C", "G"}
    assert select_in_play({"B": 2.0, "A": 2.0}, top_n=1, min_or_rvol=1.5) == {"A"}


def test_time_buckets() -> None:
    from datetime import time

    assert time_bucket(time(9, 59)) == "open"
    assert time_bucket(time(10, 0)) == "morning"
    assert time_bucket(time(13, 30)) == "afternoon"
