# Task Cards

Status: v4, 2026-11-17. Owner decision: build end to end; design calls are logged in `DECISIONS.md`.

The research core is built and tested (see "Done"). The cards below are the remaining work, **in order, one card per branch**. Rules for how to work are in `../CLAUDE.md`. "PLAN x.y" and "STRATEGIES C.n" refer to the files in this folder.

**Who does what.** Cards marked **[small]** are well specified and suited to a smaller coding model. Cards marked **[design first]** start with a design note in `docs/design/Txx.md` and stop for the owner's approval before any code.

**Definition of done for every card**

- The listed tests exist and pass; the whole suite passes (`pytest -q`) and `ruff check .` is clean, both run from `trademind/`.
- No files changed outside `trademind/`, except `.github/workflows/trademind-ci.yml`.
- The progress table is updated in the same commit.
- If the card cannot be done as written, stop and report why. Do not improvise around the spec.

## Done (research core)

| Area | Where | Tests |
|---|---|---|
| Config, enums, models, clock, logging | `shared/` | `test_config_costs_risk.py` |
| Synthetic, CSV and Parquet data; resampling; validation | `services/market_data/` | `test_data_features.py` |
| Features: VWAP, ATR, relative volume, opening range, higher-timeframe trend, day context, tags, selector | `services/feature_engine/`, `strategy_engine/view.py` | `test_data_features.py` (incl. causality) |
| Zerodha cost model | `services/paper_broker/costs.py` | PLAN 7 test vectors |
| Paper broker: base-bar fills, cancellations, gaps, MFE/MAE | `services/paper_broker/broker.py` | `test_broker.py` |
| Risk engine: fail closed, kill switch, segment overrides | `services/risk_engine/engine.py` | `test_config_costs_risk.py` |
| Strategy framework and registry | `services/strategy_engine/` | `test_strategies.py` |
| `orb_momentum` (C.1), `sweep_reversal` (C.6) | `strategy_engine/equity/` | `test_strategies.py` |
| Multi-timeframe engine, backtest runner, trap diagnostics, trials | `services/backtesting/` | `test_engine.py` (incl. no-lookahead, determinism, truncation) |
| Journal (Postgres or SQLite) | `database/` | `test_engine.py` |
| Metrics, scoreboard | `services/learning/metrics.py` | `test_metrics_api_cli.py` |
| CLI, read-only API, Docker Compose, CI | `cli.py`, `api/`, root files | `test_metrics_api_cli.py` |
| No order code guardrail | `tests/test_no_order_code.py` | itself |

## Progress

| Card | Title | Who | Status |
|---|---|---|---|
| T01 | Strategy: failed_orb_fade | small | done |
| T02 | Strategy: overextension_fade | small | done |
| T03 | Strategy: intraday_contraction | small | done |
| T04 | Strategy: first_half_hour_momentum | small | done |
| T05 | Validation and promotion gate | small | done |
| T06 | Alembic migrations | small | todo |
| T07 | Kite read-only gateway, login, instruments, history download | small | done |
| T08 | Tick-to-bar aggregator | small | done |
| T09 | Live paper runner | design first | done (`docs/design/T09-live-paper.md`) |
| T10 | Telegram notifier | small | done |
| T11 | Redis Streams event bus | design first | todo |
| T12 | AWS deployment (Terraform, EC2, SSM, backups) | design first | done (`docs/OPERATIONS.md`) |
| T13 | LLM client and daily post-mortem | design first | done (`services/ai_research/`) |
| T14 | Setup judge, shadow mode | design first | deferred until news exists (T16) |
| T15 | Weekly review and hypothesis backlog | design first | done (max two proposals, never applied) |
| T16 | News ingestion | design first | todo |
| T17 | Market regime engine | design first | done (rule-based `market_regime` tag) |
| T18 | Swing engine and swing_vcp | design first | todo |
| T19 | Dashboard | design first | done (`/dashboard` on the API) |
| T20 | Options and expiry | design first | todo |

---

## Strategy cards (T01-T04)

Follow `strategy_engine/equity/orb_momentum.py` exactly as a pattern:

- One file per strategy in `services/strategy_engine/equity/`, a `StrategyParams` subclass whose defaults equal the spec, the `@register` decorator, and an import line in `equity/__init__.py`.
- Use `view.history` (list of bar dicts) for scans, `view.opening_range(minutes)` for the opening range, `self.emitted(symbol)` for the one-signal-per-session rule, and `self.signal(...)` to build the signal. Use `buffered_stop` and `within_risk` from `base.py`.
- Set the strategy's entries in `config/strategies.yaml` to `enabled: true` (5minute and 15minute, unless the spec says one is enough).
- Tests in `tests/test_strategies.py` (or a new `tests/test_<id>.py`), built with the helpers in `tests/helpers.py` (`make_session`, `make_bars`, `frames_for`, `view_at`), must include: one positive test per side with exact `side`, `stop`, `target` and required feature keys; one negative test per numbered condition, each breaking only that condition; a state-reset test.
- After the card, run `trademind backtest --start 2025-05-01 --end 2026-04-30` once and paste the scoreboard into the card report. Do not change any parameter because of what it shows.

### T01 Strategy: failed_orb_fade [small]

Spec: STRATEGIES C.2. Extra tests: a failure after `fail_window_minutes` gives no signal; `bo_extreme` updates when price makes a new extreme after the breakout bar; a second breakout the same day is ignored.

### T02 Strategy: overextension_fade [small]

Spec: STRATEGIES C.3. Extra tests: `z` reaches the threshold two bars before the reversal trigger and still signals; four bars before does not; missing `atr14` gives no signal.

### T03 Strategy: intraday_contraction [small]

Spec: STRATEGIES C.4. `scope = "stocks"`. Extra tests: fewer than 12 prior bars gives no signal; a missing `tod_rvol` in block `b3` gives no signal; a missing bar inside the consolidation gives no signal.

### T04 Strategy: first_half_hour_momentum [small]

Spec: STRATEGIES C.5. `scope = "index"`, `allow_late_entry = True`, only a `5minute` instance. Extra engine-level test (in `tests/test_engine.py` style): entry fills at the 15:00 base bar despite `last_entry_time`, and exits `SQUAREOFF` at 15:20 when the stop is not hit. Also: no trade when `prev_close` is `None`, or when the move is below `min_move_pct`.

---

## T05 Validation and promotion gate [small]

Spec: PLAN 9.2 and 9.3.

- `services/learning/validation.py`:
  - `bootstrap_lower_bound(r: np.ndarray, confidence: float, resamples: int, seed: int) -> float`: percentile bootstrap of the mean, returns the `(1 - confidence)` quantile of resampled means.
  - `promotion_report(journal, instance_id, strategy_version, research_run_id, holdout_run_id, cfg) -> dict`: each of the five gate conditions with its value and pass/fail, plus `passed`. `k` for the Bonferroni confidence is `journal.count_trials(strategy_id, "research")`.
- `Journal.count_holdout_evals(instance_id, strategy_version) -> int` (trials with `data_split = holdout`).
- CLI `trademind validate --instance ID --start --end [--source ...]`: refuses if `start < holdout_start`, or if holdout evals for that instance version already equal `max_holdout_evals`; runs `run_backtest(..., data_split="holdout", only={ID})`; prints the promotion report against the most recent `done` research run containing that instance.

Tests: bootstrap bound is below the sample mean, deterministic for a seed, and tighter with more data; confidence uses `1 - 0.05 / k`; each gate condition can fail independently; the third holdout evaluation is refused.

## T06 Alembic migrations [small]

Add `alembic` to dependencies. `database/migrations/` with an initial revision equal to `database/models.py`. `Journal.__init__` keeps `create_all` for SQLite (tests, local) but for PostgreSQL runs `alembic upgrade head` instead. CLI `trademind db upgrade`. Test: a fresh SQLite database upgraded by Alembic has the same tables and columns as `create_all`.

## T07 Kite read-only gateway, login, instruments, history download [small]

Add `kiteconnect`. Before coding, read the installed package's own documentation for exact method names and return shapes; do not rely on this card for API details. All Kite access goes through an injected client object so tests never touch the network.

- `services/broker_gateway/kite.py`: `KiteGateway(client)` exposing only: login URL, session exchange, profile, instruments, historical candles, quotes. No other client method may be called; `tests/test_no_order_code.py` must keep passing.
- `trademind login`: prints the login URL, prompts for the `request_token`, saves `{access_token, date}` to `data/kite_token.json`. A token from an earlier date is expired.
- `KiteSource(gateway)` implementing `DataSource`: chunk requests by the per-interval window in PLAN 10 (minute: 60 days), throttle to at most 3 requests per second, retry a rate-limit error up to 3 times with backoff. Index symbols come back with zero volume.
- Instruments: download the dump once per day to `data/instruments.csv`; resolve `symbol -> instrument_token`; refresh `lot_size` and `tick_size` for universe symbols (config values stay the fallback); write upcoming expiry dates into `config/expiries.yaml` only when the owner passes `--write-expiries`.
- `trademind data download --symbols A,B|all --from --to`: base interval into the Parquet store, then `validate_bars` summary per symbol.

Tests (fake client): chunking covers the range without gaps or overlaps; throttle respected (inject a clock); retry on rate limit; stale token rejected; IST timestamps; only allowed client methods are called.

## T08 Tick-to-bar aggregator [small]

`services/market_data/aggregate.py`: `BarAggregator(session)`: `on_tick(symbol, ts, last_price, cum_volume | None) -> list[completed base bars]`, `flush(now) -> list[...]`.

- A base bar `[T, T+1m)` completes when a tick with `ts >= T+1m` arrives for that symbol, or on `flush(now)` with `now >= T+1m`.
- Bar volume is the difference in cumulative day volume between the bar's last tick and the previous bar's last tick; 0 when cumulative volume is `None`.
- An interval with no ticks produces no bar (Kite's own candles behave the same way; PLAN 4.1).
- Ticks outside the session are ignored.

Tests: OHLC from a tick sequence; volume differencing; empty interval; out-of-order tick within a bar; flush at the close.

## T09 Live paper runner [design first]

The engine runs a whole day from prepared frames (`EngineSession.run_day`). Live trading needs the same decisions computed bar by bar as data arrives. The design note must cover: an incremental step API that `run_day` itself uses (so backtest and live share one path); incremental feature updates; the parity test (replaying a recorded day through the live path gives identical trades to `run_backtest`); reconnects and gaps; daily login; shutdown at the close. This card touches the core, so it is reviewed by the owner with the stronger model.

## T10 Telegram notifier [small]

Add `httpx` as a runtime dependency. `services/notify/telegram.py`: `Notifier` with `trade_opened`, `trade_closed`, `daily_summary(markdown)`, `error(text)` via the Bot API `sendMessage`. If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is missing, every method is a no-op. Send failures are logged and never raised. Tests with a mock transport.

## T11-T20 [design first]

Each starts with `docs/design/Txx.md` (goal, interfaces, data, costs, test plan, open questions) and stops for approval. Starting points:

- **T11 Redis Streams**: BLUEPRINT 9. Streams, consumer groups, idempotent consumers; Redis is transport, the journal stays the source of truth.
- **T12 AWS deployment**: BLUEPRINT 14. Terraform for one EC2 instance in ap-south-1, Elastic IP, SSM only (no SSH), Secrets Manager, encrypted EBS and S3, Postgres backups with a tested restore, CloudWatch alarms, a monthly cost alert.
- **T13 LLM client and daily post-mortem**: PLAN 11. Bedrock first; structured output; token accounting; a monthly budget with a hard stop.
- **T14 Setup judge**: PLAN 11. No effect on trading while `judge.veto_enabled` is false, proven by a test.
- **T15 Weekly review**: at most two proposals a week, written to `docs/hypotheses/`; nothing auto-merged.
- **T16 News**: source selection is the owner's decision.
- **T17 Regime engine**: BLUEPRINT 5.7, using the context tags already logged; `UNCLASSIFIED` is valid.
- **T18 Swing**: STRATEGIES D.1, multi-day holding, delivery costs.
- **T19 Dashboard**: BLUEPRINT 13, over the read-only API; authenticated.
- **T20 Options and expiry**: option data availability, a fill model for wide spreads, time decay, contract selection, multi-leg partial fills.
