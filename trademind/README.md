# TRADEMIND

A research-first trading platform for NSE (Nifty, Bank Nifty and liquid stocks). Rule-based setups run side by side on paper, on several timeframes, every signal and trade is journalled with its market context, and a scoreboard shows which setups hold up after Zerodha's charges and slippage.

**Paper trading only.** There is no code that can place a real order, and nothing here is investment advice. No setup in this repository is known to be profitable; finding out is the point.

## What works today

- 1-minute base data from synthetic, CSV or Parquet sources, resampled to any timeframe.
- Features: VWAP, ATR, relative volume, opening range, 15- and 60-minute trend, gap, daily trend, volatility regime, stocks-in-play selection.
- Six intraday strategies, each on 5 and 15 minutes: `orb_momentum`, `failed_orb_fade`, `overextension_fade`, `intraday_contraction`, `first_half_hour_momentum`, and `sweep_reversal` (trading the stop run at yesterday's high or low).
- Validation gate: `trademind validate` checks a strategy on held-out data with a bootstrap and a multiple-testing correction.
- Real data from Zerodha Kite (read-only): daily login, instruments, history download.
- Live paper trading from Kite ticks, proven to make the same decisions as the backtest, with Telegram alerts and a Telegram-based daily login.
- AI research on AWS Bedrock (off by default): daily post-mortem and weekly review with at most two proposals, under a hard monthly budget. Advisory only.
- Market regime tag on every trade, so results can be split by market condition.
- AWS deployment: Terraform, systemd timers, nightly S3 backups.
- Paper broker with 1-minute fills, gaps, costs, slippage, MFE/MAE, and trap diagnostics: how often a stopped trade would have hit its target anyway.
- Independent risk engine that fails closed, with a kill switch.
- Journal in PostgreSQL (or SQLite locally), scoreboard by strategy and by any context tag, read-only API.

What's next is in [`docs/TASKS.md`](docs/TASKS.md). Decisions taken during the build are in [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Daily routine with real data

```bash
# once
cp .env.example .env            # KITE_API_KEY, KITE_API_SECRET, optional TELEGRAM_*
set -a; source .env; set +a
trademind data download --start 2025-05-01 --end 2025-11-14   # history for features and backtests
trademind backtest --start 2025-06-02 --end 2026-04-30 --source parquet

# every trading day, before 09:15 (or let the AWS timer do it: see docs/OPERATIONS.md)
trademind login                  # or --telegram to log in from your phone
trademind paper run              # runs until 15:30, then journals and sends a summary
```

## Run it on your laptop (no Docker)

```bash
cd trademind
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
trademind backtest --start 2025-05-01 --end 2026-04-30
trademind backtest --start 2025-05-01 --end 2026-04-30 --by time_bucket
trademind runs
```

Synthetic data is a random walk with no edge, so its scoreboard should look poor after costs. Use it to check the pipeline, not to judge strategies. Results go to `data/journal.sqlite`.

Research runs cannot read dates on or after `validation.holdout_start` in `config/settings.yaml` (default 2026-05-01). That period is reserved for out-of-sample checks.

## Run it with Docker (laptop or one EC2 instance)

```bash
cd trademind
cp .env.example .env        # set POSTGRES_PASSWORD and TRADEMIND_API_TOKEN
docker compose up -d --build
docker compose run --rm api trademind backtest --start 2025-05-01 --end 2026-04-30
curl -H "Authorization: Bearer $TRADEMIND_API_TOKEN" http://127.0.0.1:8000/runs
```

Ports bind to 127.0.0.1 only. On AWS, use a small instance in ap-south-1 (Mumbai) and reach the API through SSM port forwarding rather than opening ports. The container runs as uid 1000, so `./data` must be writable by that user.

## Commands

| Command | What it does |
|---|---|
| `trademind backtest --start --end [--source synthetic\|parquet\|csv\|kite] [--instances a@5minute,...] [--by TAG]` | Research backtest, prints the scoreboard |
| `trademind validate --instance ID --start --end` | Out-of-sample check and promotion gate (holdout dates only) |
| `trademind login` | Daily Kite login |
| `trademind paper run` | Live paper trading for today (simulated fills) |
| `trademind data download --start --end [--symbols a,b\|all]` | Kite 1-minute history into the Parquet store |
| `trademind data instruments [--write-expiries]` | Refresh the instruments dump, check lot sizes, record expiries |
| `trademind research postmortem` / `weekly` | AI notes on the latest paper day / week (needs research enabled) |
| `trademind report --run-id ID [--by TAG]` | Scoreboard of a past run |
| `trademind runs` | Recent runs |
| `trademind strategies` | Implemented strategies and configured instances |
| `trademind data synth --start --end` | Write synthetic 1-minute bars to the Parquet store |
| `trademind data validate --symbol S --start --end` | Check stored bars against the bar contract |
| `trademind api` | Serve the read-only API |

Useful `--by` tags: `market_regime`, `time_bucket`, `timeframe`, `gap_bucket`, `day_type`, `vol_regime`, `daily_trend`, `trend_60m_at_entry`, `market_trend_at_entry`, `or_width_bucket`, `is_expiry_day`.

## Configuration

| File | Holds |
|---|---|
| `config/settings.yaml` | Session times, universe, risk limits, selector, holdout date |
| `config/costs.yaml` | Zerodha charges (read 2026-11-14) and slippage. Re-check before any live use |
| `config/strategies.yaml` | Which strategy runs on which timeframe |
| `config/expiries.yaml` | Expiry dates for the expiry-day tag |

Placeholders to set yourself: index lot sizes, and the risk unit for index futures (`segment_overrides`).

## Documents

| File | What it is |
|---|---|
| [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) | Product vision and long-term architecture |
| [`docs/PLAN.md`](docs/PLAN.md) | Engineering contract: data, fills, costs, risk, validation, deviations from the blueprint |
| [`docs/STRATEGIES.md`](docs/STRATEGIES.md) | Exact rules for every feature and setup |
| [`docs/TASKS.md`](docs/TASKS.md) | Remaining work as cards |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Kite and Telegram setup, AWS deployment, daily routine, backups |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Decisions taken during the build, with reasons |
| [`CLAUDE.md`](CLAUDE.md) | Rules for the coding model working through the cards |
