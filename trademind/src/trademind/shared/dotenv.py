"""Minimal .env loader (no extra dependency): KEY=VALUE lines, never overriding real environment."""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from pathlib import Path


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        out[key] = value
    return out


def load_env_file(path: Path, environ: MutableMapping[str, str] | None = None) -> list[str]:
    """Set variables from `path` that are not already set. Returns the names it set."""
    env = os.environ if environ is None else environ
    if not path.is_file():
        return []
    added = []
    for key, value in parse_env(path.read_text(encoding="utf-8-sig")).items():
        if key not in env:
            env[key] = value
            added.append(key)
    return added
