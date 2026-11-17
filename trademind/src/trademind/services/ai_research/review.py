"""Daily post-mortem (T13) and weekly review (T15).

Both read the journal and write notes. Neither can change config, rules or trades: weekly
proposals are written as files for the owner, at most two per week, and only become real
after an owner-approved spec change, a new strategy version and a logged trial.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from trademind.database.journal import Journal, jsonable
from trademind.services.ai_research.llm import BudgetedLLM
from trademind.services.learning.metrics import scoreboard
from trademind.shared.config import AppConfig

SYSTEM = (
    "You are the research analyst for TRADEMIND, a rule-based intraday paper-trading lab for NSE. "
    "You review results; you never predict prices and never recommend real-money trades. "
    "Be specific and statistical: small samples prove nothing, so say when evidence is thin. "
    "Reply with one JSON object only, no prose outside it."
)

POSTMORTEM_KEYS = {"summary", "what_worked", "what_failed", "rule_checks", "trap_notes", "questions"}
WEEKLY_KEYS = {"summary", "patterns", "hypotheses"}

TRADE_COLS = ["instance_id", "symbol", "side", "entry_ts", "exit_ts", "exit_reason", "r_multiple",
              "net_pnl", "costs", "mfe_r", "mae_r", "post_exit_mfe_r", "target_hit_after_stop"]
CONTEXT_KEYS = ["time_bucket", "market_regime", "daily_trend", "vol_regime", "gap_bucket",
                "day_type", "market_trend_at_entry", "trend_60m_at_entry", "is_expiry_day"]


def _trade_rows(trades: pd.DataFrame, limit: int = 60) -> list[dict]:
    rows = []
    for _, t in trades.head(limit).iterrows():
        r = {c: t[c] for c in TRADE_COLS if c in t}
        r["risk_pct"] = (t.get("features") or {}).get("risk_pct")
        ctx = t.get("context") or {}
        r["context"] = {k: ctx.get(k) for k in CONTEXT_KEYS if k in ctx}
        rows.append(r)
    return jsonable(rows)


def _board(trades: pd.DataFrame, cfg: AppConfig, by: str | None = None) -> list[dict]:
    b = scoreboard(trades, cfg.settings.analytics.min_trades, by)
    keep = ["instance_id", by, "n_trades", "win_rate", "expectancy_r", "profit_factor",
            "max_drawdown_r", "cost_share", "false_breakout_rate", "stopped_then_right_rate"]
    return jsonable(b[[c for c in keep if c and c in b.columns]].to_dict("records"))


def daily_postmortem(cfg: AppConfig, journal: Journal, llm: BudgetedLLM, run_id: str,
                     reports_dir: Path) -> dict:
    run = journal.get_run(run_id)
    if run is None:
        raise ValueError(f"run {run_id} not found")
    trades = journal.read_trades(run_id)
    signals = journal.read_signals(run_id)
    rejected = (signals[~signals["approved"]]["reject_reason"].value_counts().to_dict()
                if not signals.empty else {})
    payload = {
        "day": str(run["period_start"]),
        "trades": _trade_rows(trades),
        "scoreboard": _board(trades, cfg),
        "signals": int(len(signals)),
        "rejections_by_reason": jsonable(rejected),
    }
    prompt = (
        "Review today's paper trading.\n"
        "Return JSON with keys: summary (2-3 sentences), what_worked (list), what_failed (list), "
        "rule_checks (list of anything that looks like a bug or a rule applied oddly), "
        "trap_notes (list: stops that were hit and then the target was reached anyway, i.e. "
        "post_exit_mfe_r or target_hit_after_stop), questions (list of questions for the owner).\n\n"
        f"DATA:\n{json.dumps(payload, default=str)}"
    )
    note = llm.ask_json(cfg.settings.research.routine_model, "postmortem", SYSTEM, prompt, POSTMORTEM_KEYS)
    day = run["period_start"]
    journal.log_research_note("postmortem", day, day, cfg.settings.research.routine_model, note)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / f"{day}-postmortem.md").write_text(render(f"Post-mortem {day}", note), encoding="utf-8")
    return note


def weekly_review(cfg: AppConfig, journal: Journal, llm: BudgetedLLM, start: date, end: date,
                  out_dir: Path) -> dict:
    runs = journal.read_runs_between(start, end, "live")
    frames = [journal.read_trades(r) for r in runs["run_id"]] if not runs.empty else []
    trades = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    payload = {
        "period": f"{start}..{end}",
        "sessions": int(len(runs)),
        "overall": _board(trades, cfg) if not trades.empty else [],
        "by_time_bucket": _board(trades, cfg, "time_bucket") if not trades.empty else [],
        "by_market_regime": _board(trades, cfg, "market_regime") if not trades.empty else [],
        "worst_trades": _trade_rows(trades.nsmallest(15, "r_multiple")) if not trades.empty else [],
    }
    prompt = (
        "Review this week of paper trading across strategy instances.\n"
        "Return JSON with keys: summary (3-4 sentences), patterns (list of observations, each "
        "with the evidence and the trade count behind it), hypotheses (AT MOST TWO items; each an "
        "object with keys strategy_id, change, rationale, evidence, how_to_test). A hypothesis must "
        "be a precise, testable rule change such as a filter or a parameter, never 'trade more'. "
        "If the evidence is too thin, return an empty hypotheses list.\n\n"
        f"DATA:\n{json.dumps(payload, default=str)}"
    )
    note = llm.ask_json(cfg.settings.research.deep_model, "weekly", SYSTEM, prompt, WEEKLY_KEYS)
    note["hypotheses"] = list(note.get("hypotheses") or [])[:2]  # hard cap, whatever the model says
    journal.log_research_note("weekly", start, end, cfg.settings.research.deep_model, note)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{start}_{end}-weekly.md").write_text(
        render(f"Weekly review {start} to {end}", note)
        + "\n\n_Proposals are not applied. To adopt one: write it as a spec change in "
          "docs/STRATEGIES.md with a new version, backtest it, and run `trademind validate`._\n",
        encoding="utf-8",
    )
    return note


def render(title: str, note: dict) -> str:
    lines = [f"# {title}", ""]
    for key, value in note.items():
        lines.append(f"## {key.replace('_', ' ').capitalize()}")
        if isinstance(value, list):
            lines += [f"- {json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v}"
                      for v in value] or ["- none"]
        else:
            lines.append(str(value))
        lines.append("")
    return "\n".join(lines)


def telegram_text(title: str, note: dict, limit: int = 3) -> str:
    out = [title, str(note.get("summary", ""))]
    for key in ("what_failed", "trap_notes", "hypotheses"):
        items = note.get(key) or []
        if items:
            out.append(f"{key.replace('_', ' ')}:")
            out += [f"- {i if isinstance(i, str) else i.get('change', i)}" for i in items[:limit]]
    return "\n".join(out)


def make_llm(cfg: AppConfig, journal: Journal, client=None) -> BudgetedLLM:  # noqa: ANN001
    from trademind.services.ai_research.llm import BedrockClient

    rc = cfg.settings.research
    if not rc.enabled:
        raise ValueError("research is disabled: set research.enabled and the model ids in settings.yaml")
    return BudgetedLLM(client or BedrockClient(rc.region), rc, journal)
