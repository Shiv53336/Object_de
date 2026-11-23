"""Typed configuration loaded from config/*.yaml (PLAN 3, TASKS T02)."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trademind.shared.clock import minutes_between, tf_minutes
from trademind.shared.enums import ExecutionMode, Segment
from trademind.shared.exceptions import ConfigError

CONFIG_FILES = ("settings.yaml", "costs.yaml", "strategies.yaml")
OPTIONAL_CONFIG_FILES = ("corporate_actions.yaml",)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _parse_time(value: Any) -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    raise ValueError(f"times must be quoted strings like \"09:15\", got {value!r}")


class SessionConfig(StrictModel):
    open: time
    close: time
    base_interval: str = "1minute"
    last_entry_time: time
    squareoff_time: time

    _times = field_validator(
        "open", "close", "last_entry_time", "squareoff_time", mode="before"
    )(_parse_time)

    @field_validator("base_interval")
    @classmethod
    def _base(cls, v: str) -> str:
        tf_minutes(v)
        return v

    @model_validator(mode="after")
    def _order(self) -> SessionConfig:
        if not (self.open < self.last_entry_time < self.squareoff_time < self.close):
            raise ValueError("need open < last_entry_time < squareoff_time < close")
        if minutes_between(self.open, self.close) % self.base_minutes:
            raise ValueError("session length must be a multiple of base_interval")
        return self

    @property
    def base_minutes(self) -> int:
        return tf_minutes(self.base_interval)

    @property
    def length_minutes(self) -> int:
        return minutes_between(self.open, self.close)


class InstrumentConfig(StrictModel):
    symbol: str
    exchange: str = "NSE"
    lot_size: int = Field(default=1, ge=1)
    tick_size: float = Field(default=0.05, gt=0)


class UniverseConfig(StrictModel):
    indices: list[InstrumentConfig] = []
    stocks: list[InstrumentConfig] = []


class SegmentRisk(StrictModel):
    risk_per_trade_inr: float | None = Field(default=None, gt=0)
    max_notional_inr: float | None = Field(default=None, gt=0)


class RiskConfig(StrictModel):
    risk_per_trade_inr: float = Field(gt=0)
    max_notional_inr: float = Field(gt=0)
    segment_overrides: dict[Segment, SegmentRisk] = {}
    max_trades_per_day: int = Field(ge=1)
    max_open_positions: int = Field(ge=1)
    max_consecutive_losses: int = Field(ge=1)
    daily_loss_limit_r: float = Field(lt=0)
    kill_switch: bool = False

    def limits(self, segment: Segment) -> tuple[float, float]:
        """(risk per trade, max notional) for a segment, after overrides."""
        o = self.segment_overrides.get(segment)
        risk = o.risk_per_trade_inr if o and o.risk_per_trade_inr else self.risk_per_trade_inr
        cap = o.max_notional_inr if o and o.max_notional_inr else self.max_notional_inr
        return risk, cap


class SelectorConfig(StrictModel):
    top_n: int = Field(ge=1)
    min_or_rvol: float = Field(gt=0)
    or_minutes: int = Field(gt=0)


class BacktestConfig(StrictModel):
    warmup_days: int = Field(ge=0)


class AnalyticsConfig(StrictModel):
    min_trades: int = Field(ge=1)


class ValidationConfig(StrictModel):
    holdout_start: date
    holdout_end: date
    bootstrap_resamples: int = 10000
    bootstrap_seed: int = 7
    min_research_trades: int = 100
    max_drawdown_r: float = 15
    min_holdout_trades: int = 30
    max_holdout_evals: int = 2
    min_session_coverage: float = Field(default=0.9, gt=0, le=1)

    @model_validator(mode="after")
    def _window(self) -> ValidationConfig:
        if self.holdout_end <= self.holdout_start:
            raise ValueError("validation.holdout_end must be after holdout_start")
        return self

    @property
    def window(self) -> tuple[date, date]:
        return self.holdout_start, self.holdout_end


class ModelPrice(StrictModel):
    input_per_mtok_usd: float = Field(ge=0)
    output_per_mtok_usd: float = Field(ge=0)


class ResearchConfig(StrictModel):
    """AI research layer (PLAN 11). Advisory only: it never changes rules or trades."""

    enabled: bool = False
    provider: str = "bedrock"
    region: str = "ap-south-1"
    routine_model: str = ""
    deep_model: str = ""
    monthly_budget_usd: float = Field(default=15.0, gt=0)
    max_output_tokens: int = Field(default=1500, gt=0)
    prices: dict[str, ModelPrice] = {}

    @model_validator(mode="after")
    def _models_when_enabled(self) -> ResearchConfig:
        if self.enabled and not (self.routine_model and self.deep_model):
            raise ValueError("research.enabled needs routine_model and deep_model (Bedrock model ids)")
        for m in (self.routine_model, self.deep_model):
            if m and m not in self.prices:
                raise ValueError(f"research.prices has no entry for model {m!r}")
        return self


class ExecutionConfig(StrictModel):
    mode: ExecutionMode = ExecutionMode.PAPER

    @field_validator("mode")
    @classmethod
    def _paper_only(cls, v: ExecutionMode) -> ExecutionMode:
        if v != ExecutionMode.PAPER:
            raise ValueError("only PAPER execution is enabled in this version (BLUEPRINT 12.3)")
        return v


class Settings(StrictModel):
    timezone: str = "Asia/Kolkata"
    session: SessionConfig
    market_symbol: str
    universe: UniverseConfig
    risk: RiskConfig
    selector: SelectorConfig
    backtest: BacktestConfig
    analytics: AnalyticsConfig
    validation: ValidationConfig
    execution: ExecutionConfig = ExecutionConfig()
    research: ResearchConfig = ResearchConfig()

    @model_validator(mode="after")
    def _market_in_universe(self) -> Settings:
        symbols = [i.symbol for i in self.universe.indices + self.universe.stocks]
        if len(symbols) != len(set(symbols)):
            raise ValueError("duplicate symbol in universe")
        if self.market_symbol not in symbols:
            raise ValueError("market_symbol must be in the universe")
        if self.selector.or_minutes % self.session.base_minutes:
            raise ValueError("selector.or_minutes must be a multiple of base_interval")
        return self


class SegmentCost(StrictModel):
    brokerage_pct: float = 0.0
    brokerage_cap: float | None = None
    brokerage_flat: float | None = None
    stt_buy: float = 0.0
    stt_sell: float = 0.0
    txn: float = 0.0
    sebi_per_crore: float = 10.0
    stamp_buy: float = 0.0


class CostsConfig(StrictModel):
    gst: float
    segments: dict[Segment, SegmentCost]
    slippage_bps: dict[Segment, float]

    @model_validator(mode="after")
    def _complete(self) -> CostsConfig:
        for seg in Segment:
            if seg not in self.segments or seg not in self.slippage_bps:
                raise ValueError(f"costs.yaml is missing segment {seg}")
        return self


class StrategyInstanceConfig(StrictModel):
    id: str
    timeframe: str
    enabled: bool = True
    params: dict[str, Any] = {}

    @field_validator("timeframe")
    @classmethod
    def _tf(cls, v: str) -> str:
        tf_minutes(v)
        return v

    @property
    def instance_id(self) -> str:
        return f"{self.id}@{self.timeframe}"


class StrategiesConfig(StrictModel):
    instances: list[StrategyInstanceConfig] = []

    @model_validator(mode="after")
    def _unique(self) -> StrategiesConfig:
        ids = [i.instance_id for i in self.instances]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate strategy instance (same id and timeframe)")
        return self


class CorporateAction(StrictModel):
    """A split or bonus: prices before `ex_date` are divided by `ratio` (2 for a 1:1 bonus or a
    2-for-1 split) and volumes multiplied by it, so history is comparable across the event."""

    symbol: str
    ex_date: date
    ratio: float = Field(gt=0)
    note: str = ""


class CorporateActionsConfig(StrictModel):
    actions: list[CorporateAction] = []


@dataclass(frozen=True)
class AppConfig:
    settings: Settings
    costs: CostsConfig
    strategies: StrategiesConfig
    expiries: dict[str, list[date]]
    config_dir: Path
    corporate_actions: tuple[CorporateAction, ...] = ()


def _read_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config(config_dir: str | Path | None = None) -> AppConfig:
    cdir = Path(config_dir or os.environ.get("TRADEMIND_CONFIG_DIR", "config"))
    try:
        settings = Settings.model_validate(_read_yaml(cdir / "settings.yaml"))
        costs = CostsConfig.model_validate(_read_yaml(cdir / "costs.yaml"))
        strategies = StrategiesConfig.model_validate(_read_yaml(cdir / "strategies.yaml"))
        raw_exp = _read_yaml(cdir / "expiries.yaml") if (cdir / "expiries.yaml").exists() else {}
        ca_path = cdir / "corporate_actions.yaml"
        actions = CorporateActionsConfig.model_validate(_read_yaml(ca_path) or {}) if ca_path.exists() \
            else CorporateActionsConfig()
    except FileNotFoundError as exc:
        raise ConfigError(f"missing config file: {exc.filename}") from exc
    expiries = {str(k): sorted(date.fromisoformat(str(d)) for d in (v or [])) for k, v in raw_exp.items()}
    base = settings.session.base_minutes
    for inst in strategies.instances:
        if tf_minutes(inst.timeframe) % base:
            raise ConfigError(f"{inst.instance_id}: timeframe must be a multiple of the base interval")
    return AppConfig(settings, costs, strategies, expiries, cdir, tuple(actions.actions))


def config_hash(config_dir: str | Path) -> str:
    h = hashlib.sha256()
    present = [n for n in OPTIONAL_CONFIG_FILES if (Path(config_dir) / n).exists()]
    for name in (*CONFIG_FILES, *present):
        # Line endings normalised, so a Windows checkout hashes like the server's.
        h.update((Path(config_dir) / name).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


@dataclass(frozen=True)
class RuntimePaths:
    data_dir: Path
    bars_dir: Path  # exchange candles only: research, validation, live history
    database_url: str

    @property
    def live_bars_dir(self) -> Path:
        return self.data_dir / "bars_live"

    @property
    def synthetic_bars_dir(self) -> Path:
        return self.data_dir / "bars_synthetic"


def runtime_paths() -> RuntimePaths:
    data_dir = Path(os.environ.get("TRADEMIND_DATA_DIR", "data"))
    url = os.environ.get("TRADEMIND_DATABASE_URL") or f"sqlite:///{(data_dir / 'journal.sqlite').as_posix()}"
    return RuntimePaths(data_dir=data_dir, bars_dir=data_dir / "bars", database_url=url)
