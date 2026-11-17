# Rules for working in `trademind/`

TRADEMIND is a research-first trading platform for NSE that runs on paper only. `docs/BLUEPRINT.md` is the product vision; `docs/PLAN.md` is the engineering contract; `docs/STRATEGIES.md` holds exact trading rules; `docs/TASKS.md` lists the remaining work.

## How to work

1. Open `docs/TASKS.md` and take the first card whose status is `todo`. Do that card and only that card.
2. Read the PLAN and STRATEGIES sections the card cites, and the existing code it builds on, before writing code.
3. Write the listed tests, then the code, until `pytest -q` and `ruff check .` both pass from `trademind/`.
4. Mark the card `done` in the progress table in the same commit.
5. One card per branch, named `tm/Txx-short-name`. Commit message: `Txx: <what changed>`.
6. Cards marked "design first" produce `docs/design/Txx.md` only. Stop there and wait for the owner.

## Hard rules

- **Never write code that places, modifies or cancels real orders.** Broker access is read-only. `tests/test_no_order_code.py` enforces this; never weaken, skip or delete it.
- **Only PAPER execution.** Do not add or enable other execution modes.
- **Never commit secrets.** Keys and tokens live in `.env` and `data/`, both gitignored. If you see a secret in a diff, stop and tell the owner.
- **Stay inside `trademind/`.** The only files allowed elsewhere are `.github/workflows/trademind-ci.yml` and `.github/workflows/trademind-agent.yml`. Never touch `expense-tracker/` or its workflow.
- **The specs are the source of truth.** If a spec is ambiguous, contradictory or looks wrong, stop and ask. Do not pick an interpretation silently, and do not edit `PLAN.md` or `STRATEGIES.md` to match your code.
- **No new dependencies** beyond those a card names.
- **No lookahead.** A decision at a bar's close uses only data up to that bar. New features need a causality test (PLAN 5.4).
- **Deterministic by default.** Anything random takes an explicit seed. Tests never use the network, the wall clock or real credentials.
- **Do not tune.** Never change a strategy parameter, threshold or rule to make results look better. Parameters change only through an owner-approved spec change with a new strategy `version`.
- **Do not read holdout data** except through `trademind validate` (PLAN 9.2).
- **Never weaken the agent guardrails** (`.claude/settings.json`, `deploy/agent/sudoers`, `tests/test_agent_harness.py`, the agent workflow) unless the owner asks for that change.
- **Do not change the core** (`backtesting/session.py`, `paper_broker/broker.py`, `risk_engine/engine.py`, `strategy_engine/view.py`) unless the card says so. If a card seems to need it, stop and ask.

## Running as the ops agent

When the `trademind-agent` workflow starts you (docs/AGENT.md), the request in the prompt replaces step 1 above: do that request, not the next card, unless it asks for a card. You cannot push or deploy; commit on the branch you are given and the workflow opens the pull request. End with the short report the prompt asks for.

## Conventions

- Python 3.11+, type hints on public functions, ruff clean, line length 110.
- Timestamps are timezone-aware Asia/Kolkata in the engine and UTC in the database. A bar's `ts` is its open time.
- Prices and P&L are `float`; do not round inside calculations. Format only when printing.
- Enumerations are `StrEnum`; rejection and exit reasons are the closed sets in PLAN 6 and 4.5.
- Tests: pytest, one behaviour per test, hand-built data with round numbers so a person can check the expected values.
- No commented-out code, no leftover `print`, no TODO without a card number.

## Useful commands

```
pip install -e ".[dev]"
pytest -q
ruff check .
trademind strategies
trademind backtest --start 2025-05-01 --end 2026-04-30 --by time_bucket
```

## When you finish a card, report

- The card, and the files changed.
- Test count and result.
- Anything in the spec that was unclear.
- Anything a later card should know.
