"""Data integrity: separate stores, atomic writes, corporate-action adjustment and detection."""

from __future__ import annotations

import dataclasses
from datetime import date

import pandas as pd
import pytest
from typer.testing import CliRunner

from tests.conftest import CONFIG_DIR
from trademind.cli import app
from trademind.services.market_data.adjust import AdjustedSource, adjust_bars, overnight_jumps
from trademind.services.market_data.store import ParquetStore
from trademind.shared.clock import IST
from trademind.shared.config import CorporateAction, config_hash, load_config, runtime_paths


def _two_days(price_day2: float) -> pd.DataFrame:
    ts = [pd.Timestamp("2025-09-02 09:15", tz=IST), pd.Timestamp("2025-09-02 15:29", tz=IST),
          pd.Timestamp("2025-09-03 09:15", tz=IST)]
    return pd.DataFrame({"ts": ts, "open": [100.0, 100.0, price_day2], "high": [101.0, 101.0, price_day2],
                         "low": [99.0, 99.0, price_day2], "close": [100.0, 100.0, price_day2],
                         "volume": [10, 20, 40]})


ACTION = CorporateAction(symbol="AAA", ex_date=date(2025, 9, 3), ratio=2)


def test_adjust_divides_prices_and_multiplies_volume_before_ex_date() -> None:
    out = adjust_bars(_two_days(50.0), [ACTION])
    assert out["close"].tolist() == [50.0, 50.0, 50.0]
    assert out["volume"].tolist() == [20, 40, 40]


def test_jumps_are_found_and_vanish_once_adjusted() -> None:
    raw = _two_days(50.0)
    assert overnight_jumps(raw) == [(date(2025, 9, 3), pytest.approx(0.5))]
    assert overnight_jumps(adjust_bars(raw, [ACTION])) == []
    assert overnight_jumps(_two_days(110.0)) == []


def test_adjusted_source_wraps_a_store(tmp_path) -> None:
    store = ParquetStore(tmp_path)
    store.write("AAA", "1minute", _two_days(50.0))
    src = AdjustedSource(store, [ACTION])
    assert src.read("AAA", "1minute", date(2025, 9, 2), date(2025, 9, 3))["close"].max() == 50.0
    assert src.sessions("AAA", "1minute") == [date(2025, 9, 2), date(2025, 9, 3)]


def test_corporate_actions_load_and_change_the_config_hash(tmp_path) -> None:
    for f in CONFIG_DIR.iterdir():
        if f.is_file():
            (tmp_path / f.name).write_bytes(f.read_bytes())
    before = config_hash(tmp_path)
    (tmp_path / "corporate_actions.yaml").write_text(
        'actions:\n  - {symbol: AAA, ex_date: "2025-09-03", ratio: 2}\n', encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.corporate_actions == (ACTION,)
    assert config_hash(tmp_path) != before


def test_store_write_is_atomic_and_leaves_no_temp_files(tmp_path) -> None:
    store = ParquetStore(tmp_path)
    store.write("AAA", "1minute", _two_days(50.0))
    store.write("AAA", "1minute", _two_days(60.0))
    files = sorted(p.name for p in (tmp_path / "1minute").iterdir())
    assert files == ["AAA.parquet"]
    assert store.read("AAA", "1minute", date(2025, 9, 3), date(2025, 9, 3))["close"].tolist() == [60.0]


def test_synthetic_data_never_lands_in_the_research_store() -> None:
    r = CliRunner().invoke(app, ["data", "synth", "--start", "2025-09-01", "--end", "2025-09-02"])
    assert r.exit_code == 0, r.output
    paths = runtime_paths()
    assert any(paths.synthetic_bars_dir.rglob("*.parquet"))
    assert not paths.bars_dir.exists() or not any(paths.bars_dir.rglob("*.parquet"))


def test_data_validate_flags_a_possible_split(cfg) -> None:
    store = ParquetStore(runtime_paths().bars_dir)
    stock = cfg.settings.universe.stocks[0].symbol
    store.write(stock, "1minute", _two_days(50.0))
    r = CliRunner().invoke(app, ["data", "validate", "--symbol", stock, "--source", "parquet",
                                 "--start", "2025-09-02", "--end", "2025-09-03"])
    assert r.exit_code == 1 and "possible split or bonus on 2025-09-03" in r.output


def test_cfg_replace_keeps_actions(cfg) -> None:
    assert dataclasses.replace(cfg, corporate_actions=(ACTION,)).corporate_actions == (ACTION,)
