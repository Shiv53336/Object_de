"""Guardrail: no code in src/ may place, modify or cancel real orders (PLAN 10). Never weaken."""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

FORBIDDEN = re.compile(r"place_order|modify_order|cancel_order|place_gtt|/orders\b")


def test_no_real_order_code() -> None:
    offenders = [p for p in SRC.rglob("*.py") if FORBIDDEN.search(p.read_text(encoding="utf-8"))]
    assert offenders == [], f"order-placement code found in {offenders}"


