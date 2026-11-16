"""Strategy registry: id -> class, and building configured instances."""

from __future__ import annotations

import importlib

from trademind.services.strategy_engine.base import Strategy
from trademind.shared.config import StrategiesConfig
from trademind.shared.exceptions import ConfigError

_REGISTRY: dict[str, type[Strategy]] = {}


def register(cls: type[Strategy]) -> type[Strategy]:
    if cls.id in _REGISTRY and _REGISTRY[cls.id] is not cls:
        raise ValueError(f"duplicate strategy id {cls.id}")
    _REGISTRY[cls.id] = cls
    return cls


def _load_builtin() -> None:
    importlib.import_module("trademind.services.strategy_engine.equity")


def available() -> list[str]:
    _load_builtin()
    return sorted(_REGISTRY)


def build_instances(cfg: StrategiesConfig, only: set[str] | None = None) -> list[Strategy]:
    """Enabled instances, sorted by instance id. `only` restricts to given instance ids."""
    _load_builtin()
    out: list[Strategy] = []
    for ic in cfg.instances:
        if not ic.enabled or (only is not None and ic.instance_id not in only):
            continue
        cls = _REGISTRY.get(ic.id)
        if cls is None:
            raise ConfigError(f"enabled strategy {ic.id!r} is not implemented")
        out.append(cls(ic.timeframe, ic.params))
    if only is not None:
        missing = only - {s.instance_id for s in out}
        if missing:
            raise ConfigError(f"unknown or disabled strategy instances: {sorted(missing)}")
    return sorted(out, key=lambda s: s.instance_id)
