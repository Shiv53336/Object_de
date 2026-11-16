"""LLM access for research (BLUEPRINT 6). Never on the trading path.

`BudgetedLLM` wraps any client: it refuses calls once month-to-date spend reaches the cap,
records every call's tokens and cost in the journal, and parses JSON replies.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from trademind.database.journal import Journal
from trademind.shared.config import ResearchConfig
from trademind.shared.exceptions import TrademindError


class BudgetExceeded(TrademindError):
    pass


class LLMError(TrademindError):
    pass


@dataclass(frozen=True)
class LLMReply:
    text: str
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    def complete(self, model: str, system: str, prompt: str, max_tokens: int) -> LLMReply: ...


class BedrockClient:
    """Amazon Bedrock Converse API. Credentials come from the instance role or the environment."""

    def __init__(self, region: str, client: Any = None) -> None:
        if client is None:
            import boto3  # lazily: only research needs it

            client = boto3.client("bedrock-runtime", region_name=region)
        self.client = client

    def complete(self, model: str, system: str, prompt: str, max_tokens: int) -> LLMReply:
        resp = self.client.converse(
            modelId=model,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
        )
        parts = resp["output"]["message"]["content"]
        text = "".join(p.get("text", "") for p in parts)
        usage = resp.get("usage", {})
        return LLMReply(text, int(usage.get("inputTokens", 0)), int(usage.get("outputTokens", 0)))


def extract_json(text: str) -> dict:
    """First JSON object in the reply (models sometimes wrap it in prose or code fences)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, ValueError) as exc:
        raise LLMError("reply was not valid JSON") from exc
    if not isinstance(data, dict):
        raise LLMError("reply JSON is not an object")
    return data


class BudgetedLLM:
    def __init__(self, client: LLMClient, cfg: ResearchConfig, journal: Journal,
                 now: Any = None) -> None:
        self.client, self.cfg, self.journal = client, cfg, journal
        self.now = now or (lambda: datetime.now(UTC))

    def month_to_date(self) -> float:
        n = self.now()
        return self.journal.llm_cost_since(datetime(n.year, n.month, 1, tzinfo=UTC))

    def cost(self, model: str, reply: LLMReply) -> float:
        p = self.cfg.prices[model]
        return (reply.input_tokens * p.input_per_mtok_usd + reply.output_tokens * p.output_per_mtok_usd) / 1e6

    def ask_json(self, model: str, use_case: str, system: str, prompt: str, required: set[str]) -> dict:
        spent = self.month_to_date()
        if spent >= self.cfg.monthly_budget_usd:
            raise BudgetExceeded(
                f"LLM budget reached: ${spent:.2f} of ${self.cfg.monthly_budget_usd:.2f} this month"
            )
        reply = self.client.complete(model, system, prompt, self.cfg.max_output_tokens)
        self.journal.log_llm_usage(model, use_case, reply.input_tokens, reply.output_tokens,
                                   self.cost(model, reply))
        data = extract_json(reply.text)
        missing = required - set(data)
        if missing:
            raise LLMError(f"reply is missing keys: {sorted(missing)}")
        return data
