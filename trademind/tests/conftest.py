from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from trademind.shared.config import AppConfig, InstrumentConfig, load_config

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture(scope="session")
def cfg() -> AppConfig:
    return load_config(CONFIG_DIR)


@pytest.fixture(scope="session")
def small_cfg(cfg: AppConfig) -> AppConfig:
    """Market index plus two stocks, short warmup: fast engine tests."""
    s = cfg.settings
    universe = s.universe.model_copy(
        update={"stocks": [InstrumentConfig(symbol="AAA"), InstrumentConfig(symbol="BBB")]}
    )
    settings = s.model_copy(
        update={
            "universe": universe,
            "backtest": s.backtest.model_copy(update={"warmup_days": 45}),
        }
    )
    return dataclasses.replace(cfg, settings=settings)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRADEMIND_CONFIG_DIR", str(CONFIG_DIR))
    monkeypatch.setenv("TRADEMIND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("TRADEMIND_DATABASE_URL", raising=False)
    monkeypatch.setenv("TRADEMIND_LOG_JSON", "0")
