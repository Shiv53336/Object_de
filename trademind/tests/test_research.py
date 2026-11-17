from __future__ import annotations

import dataclasses
import json
from datetime import UTC, date, datetime

import pytest

from trademind.database.journal import Journal
from trademind.services.ai_research.llm import (
    BedrockClient,
    BudgetedLLM,
    BudgetExceeded,
    LLMError,
    LLMReply,
    extract_json,
)
from trademind.services.ai_research.review import daily_postmortem, telegram_text, weekly_review
from trademind.services.backtesting.runner import run_backtest
from trademind.services.feature_engine.context import market_regime
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.market_data.synthetic import SyntheticSource
from trademind.services.strategy_engine.equity.orb_momentum import OrbMomentum
from trademind.services.strategy_engine.equity.sweep_reversal import SweepReversal
from trademind.shared.config import AppConfig, ModelPrice

MODEL = "test-model"


def _cfg(cfg: AppConfig, budget: float = 5.0) -> AppConfig:
    rc = cfg.settings.research.model_copy(update={
        "enabled": True, "routine_model": MODEL, "deep_model": MODEL, "monthly_budget_usd": budget,
        "prices": {MODEL: ModelPrice(input_per_mtok_usd=2.0, output_per_mtok_usd=10.0)},
    })
    return dataclasses.replace(cfg, settings=cfg.settings.model_copy(update={"research": rc}))


class FakeLLM:
    def __init__(self, reply: dict | str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, model, system, prompt, max_tokens) -> LLMReply:
        self.prompts.append(prompt)
        body = self.reply if isinstance(self.reply, str) else json.dumps(self.reply)
        text = body if isinstance(self.reply, str) else f"Here you go:\n```json\n{body}\n```"
        return LLMReply(text, 100_000, 10_000)


POSTMORTEM = {"summary": "ok", "what_worked": ["a"], "what_failed": ["b"], "rule_checks": [],
              "trap_notes": ["stop hit then target"], "questions": []}
WEEKLY = {"summary": "s", "patterns": ["p"], "hypotheses": [
    {"strategy_id": "x", "change": f"c{i}", "rationale": "r", "evidence": "e", "how_to_test": "t"}
    for i in range(4)]}


def test_extract_json_variants() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('blah ```json\n{"a": 2}\n``` tail') == {"a": 2}
    assert extract_json('Sure! {"a": 3} hope that helps') == {"a": 3}
    with pytest.raises(LLMError):
        extract_json("no json here")


def test_budget_guard_records_and_stops(cfg: AppConfig, tmp_path) -> None:
    c = _cfg(cfg, budget=0.5)
    j = Journal(f"sqlite:///{tmp_path / 'j.sqlite'}")
    llm = BudgetedLLM(FakeLLM({"summary": "x"}), c.settings.research, j)
    assert llm.ask_json(MODEL, "test", "sys", "p", {"summary"}) == {"summary": "x"}
    assert llm.month_to_date() == pytest.approx(0.3)  # 0.1M in x $2 + 0.01M out x $10
    llm.ask_json(MODEL, "test", "sys", "p", {"summary"})
    with pytest.raises(BudgetExceeded):
        llm.ask_json(MODEL, "test", "sys", "p", {"summary"})
    next_month = BudgetedLLM(FakeLLM({"summary": "x"}), c.settings.research, j,
                             now=lambda: datetime(2099, 1, 1, tzinfo=UTC))
    assert next_month.month_to_date() == 0.0


def test_missing_keys_rejected(cfg: AppConfig, tmp_path) -> None:
    j = Journal(f"sqlite:///{tmp_path / 'j.sqlite'}")
    llm = BudgetedLLM(FakeLLM({"summary": "x"}), _cfg(cfg).settings.research, j)
    with pytest.raises(LLMError, match="missing keys"):
        llm.ask_json(MODEL, "t", "s", "p", {"summary", "hypotheses"})


def test_research_disabled_by_default_and_needs_models(cfg: AppConfig) -> None:
    assert cfg.settings.research.enabled is False
    with pytest.raises(ValueError, match="routine_model"):
        cfg.settings.research.model_validate({"enabled": True})


def _run(cfg: AppConfig, tmp_path) -> tuple[Journal, str]:
    s = cfg.settings
    j = Journal(f"sqlite:///{tmp_path / 'j.sqlite'}")
    src = SyntheticSource(7, build_instruments(s), s.session, s.market_symbol)
    rid = run_backtest(cfg, src, date(2025, 9, 1), date(2025, 9, 3), j,
                       strategies=[OrbMomentum("5minute"), SweepReversal("5minute")])
    return j, rid


def test_daily_postmortem_writes_note_and_report(small_cfg: AppConfig, tmp_path) -> None:
    c = _cfg(small_cfg)
    j, rid = _run(c, tmp_path)
    fake = FakeLLM(POSTMORTEM)
    note = daily_postmortem(c, j, BudgetedLLM(fake, c.settings.research, j), rid, tmp_path / "reports")
    assert note["trap_notes"] == ["stop hit then target"]
    assert (tmp_path / "reports" / "2025-09-01-postmortem.md").exists()
    payload = json.loads(fake.prompts[0].split("DATA:\n", 1)[1])
    assert {"trades", "scoreboard", "rejections_by_reason"} <= set(payload)
    assert "market_regime" in payload["trades"][0]["context"]
    assert "TRADEMIND" in telegram_text("TRADEMIND post-mortem", note)


def test_weekly_review_caps_hypotheses(small_cfg: AppConfig, tmp_path) -> None:
    c = _cfg(small_cfg)
    j = Journal(f"sqlite:///{tmp_path / 'j.sqlite'}")
    note = weekly_review(c, j, BudgetedLLM(FakeLLM(WEEKLY), c.settings.research, j),
                         date(2025, 9, 1), date(2025, 9, 5), tmp_path / "research")
    assert len(note["hypotheses"]) == 2
    text = (tmp_path / "research" / "2025-09-01_2025-09-05-weekly.md").read_text()
    assert "Proposals are not applied" in text


def test_market_regime_rules() -> None:
    assert market_regime({"vol_regime": "unknown", "daily_trend": "up"}) == "UNCLASSIFIED"
    assert market_regime({"vol_regime": "high", "daily_trend": "up"}) == "HIGH_VOLATILITY"
    assert market_regime({"vol_regime": "normal", "daily_trend": "up"}) == "BULLISH_TREND"
    assert market_regime({"vol_regime": "normal", "daily_trend": "down"}) == "BEARISH_TREND"
    assert market_regime({"vol_regime": "low", "daily_trend": "flat"}) == "LOW_VOLATILITY"
    assert market_regime({"vol_regime": "normal", "daily_trend": "flat"}) == "SIDEWAYS"


def test_bedrock_client_uses_converse() -> None:
    class Stub:
        def converse(self, **kw):
            self.kw = kw
            return {"output": {"message": {"content": [{"text": '{"a": 1}'}]}},
                    "usage": {"inputTokens": 12, "outputTokens": 3}}

    stub = Stub()
    reply = BedrockClient("ap-south-1", client=stub).complete("m", "sys", "hi", 100)
    assert reply == LLMReply('{"a": 1}', 12, 3)
    assert stub.kw["modelId"] == "m" and stub.kw["inferenceConfig"]["temperature"] == 0
