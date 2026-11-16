# TRADEMIND: Engineering Plan

Status: v3, 2026-11-16. Owner: Shivprakash.

`BLUEPRINT.md` is the product vision: what TRADEMIND becomes. This file is the engineering contract for what is built now: exact data shapes, fill rules, costs, risk and validation. Where the two differ, this file states the deviation and the reason (section 1.3). `STRATEGIES.md` holds the exact trading rules; `TASKS.md` holds the remaining work as cards.

Read order for an implementer: `../CLAUDE.md` (rules), this file, `STRATEGIES.md`, `TASKS.md`.

v3 changes: renamed to TRADEMIND, adopted the blueprint's module layout, journal on PostgreSQL (SQLite for local runs and tests), Docker Compose packaging, read-only API, per-segment risk overrides, `kill_switch` and `invalid_input` rejections. v2 changes: 1-minute base data, timeframe as a strategy parameter, higher-timeframe context, fills on base bars, trap diagnostics.

---

## 1. What we are building

TRADEMIND, built research-first. The blueprint's own principle sets the order: "Build the intelligence first. Prove the edge second. Automate execution last."

- Many rule-based setups run in parallel on paper ("shadow accounts"), each on one or more timeframes.
- Every signal, approved or rejected, and every trade is journalled with its market context.
- A scoreboard measures which setup works in which conditions, after costs.
- A research layer (LLM) reviews results and proposes new rules, which must pass a backtest and a held-out test before adoption.
- Real money is out of scope until the blueprint's Phase 14 gate. See section 10.

### 1.1 Principles

1. **Code trades, the LLM researches.** Signals, sizing, risk and fills are deterministic code. The LLM never sits in the per-bar loop.
2. **One code path.** Backtest and live paper trading run the same strategy, risk, broker and journal code. Only the data feed differs.
3. **No lookahead.** A decision at bar close may use only data up to and including that bar. This is enforced by tests.
4. **Costs are first-class.** Every result is reported net of brokerage, taxes and slippage.
5. **Every experiment is counted.** Each backtest is logged as a trial. More trials means a stricter bar for calling something an edge.
6. **Statistics judge, not stories.** No rule is adopted because it sounds right.
7. **Timeframe is a parameter, not an assumption.** Data is stored at 1 minute; each setup can run on several timeframes side by side, and the scoreboard compares them.
8. **Traps are measured, not feared.** Stops at obvious levels get hit often. The lab records how often a stopped trade would have worked, and trades the trap itself as a setup.
9. **Fail closed.** Missing or invalid inputs to risk are rejections, never approvals.

### 1.2 Non-goals for now

- Placing real orders. No order-placement code exists (guarded by a test).
- Options pricing, Greeks and option-chain strategies (T20, design first).
- An Android app. Phone access is Telegram alerts first, then a web dashboard.
- Predicting prices with an LLM.

### 1.3 Deviations from BLUEPRINT.md, and why

| Blueprint | Now | Reason |
|---|---|---|
| Sprint order: infra, broker, live data, then strategies and backtests | Research core first: backtest, paper broker, risk, journal, two strategies | Learn whether any setup has an edge before building live plumbing |
| Redis Streams from Sprint 1 | Compose service behind the `live` profile, unused until the live runner (T09, T11) | Backtests need no event bus |
| TimescaleDB hypertables for candles | Bars in Parquet; Postgres (Timescale image) holds the journal | Parquet is faster for research reads; hypertables arrive with live candles |
| Decimal for financial values | float64 in the engine and journal | Analytics, not a ledger. A Decimal orders/fills ledger comes with live execution |
| `BrokerGateway` with `place_order` and friends | Read-only gateway only (T07) | No order code until the Phase 14 gate |
| Alembic migrations | `create_all` at startup; Alembic in T06 | Schema still moving |
| `all_cash_fno` dynamic universe | 2 indices and 10 stocks in config | Point-in-time universe snapshots come with real data (T07) |
| Regime engine before strategies | Context tags (day type, volatility, trend) logged on every trade | Let the scoreboard show which regimes matter before encoding them (T17) |

---

## 2. Scope and status

| Blueprint phase | What exists now | Next |
|---|---|---|
| 0 Foundation | Package, config, JSON logging, tests, CI, Docker Compose, API health | - |
| 1 Infrastructure and database | Postgres (Timescale image) journal via SQLAlchemy; SQLite fallback | Alembic (T06), Redis (T11) |
| 2 Broker and instruments | Instruments from config | Kite read-only gateway, login, instruments dump (T07) |
| 3 Market data pipeline | Synthetic, CSV and Parquet sources; validation | Historical download (T07), ticks to bars (T08) |
| 4 Candle and feature engine | Resampling from 1-minute base; VWAP, ATR, relative volume, opening range, higher-timeframe trend, day context | - |
| 5 Regime engine | Context tags only | T17 |
| 6 Strategy engine | Framework, registry, `orb_momentum`, `sweep_reversal` | Four more intraday setups (T01-T04) |
| 7 Backtesting | Multi-timeframe engine, costs, slippage, journal, trials, scoreboard | Validation and promotion gate (T05) |
| 8 Ranking and risk | Independent fail-closed risk engine, kill switch | Signal ranker (later) |
| 9 Paper execution | Paper broker with base-bar fills, MFE/MAE, trap diagnostics | Live paper runner (T09) |
| 10 AI research | - | T13-T16 |
| 11 Dashboard | Read-only API | T19 |
| 12 AWS deployment | Compose file that runs unchanged on one EC2 instance | T12 |
| 13-14 Shadow and live | - | After the gates in section 9 |

---

## 3. Architecture

```
  DataSource (synthetic | csv | parquet | kite later)
        |
        v
  Feature engine: base features, higher-timeframe trend, resample to each timeframe,
                  timeframe features, day context, opening stats
        |
        v
  EngineSession: base-bar clock (375 one-minute steps per session)
        |   at each timeframe close: BarView -> Strategy.on_bar -> Signal
        v
  RiskEngine (independent, fail closed) -> approve and size, or reject with a reason
        |
        v
  PaperBroker: fills on base bars, costs, slippage, MFE/MAE  -> Trade
        |
        v
  Journal (Postgres or SQLite): runs, signals, trades, day_context, trials
        |
        v
  Learning: metrics, scoreboard, trap diagnostics  ->  CLI and read-only API
```

### 3.1 Code layout (under `trademind/`)

```
trademind/
  CLAUDE.md, README.md, pyproject.toml, Dockerfile, docker-compose.yml, .env.example
  config/                 settings.yaml, costs.yaml, strategies.yaml, expiries.yaml
  docs/                   BLUEPRINT.md, PLAN.md, STRATEGIES.md, TASKS.md
  src/trademind/
    shared/               config, enums, models, clock, logging, exceptions
    services/
      instrument_registry/  registry.py
      market_data/          source.py, synthetic.py, store.py (Parquet, CSV), resample.py
      feature_engine/       indicators.py, htf.py, context.py, selector.py
      strategy_engine/      view.py, base.py, registry.py, equity/<one file per strategy>
      risk_engine/          engine.py
      paper_broker/         costs.py, broker.py
      backtesting/          dataset.py, session.py, runner.py
      learning/             metrics.py
    database/             models.py (SQLAlchemy tables), journal.py
    api/                  main.py (FastAPI, read-only)
    cli.py
  tests/
  data/                   gitignored: bars/, journal.sqlite
```

### 3.2 Technology

- Python 3.11+ (Docker image uses 3.12). Package `trademind`, `src/` layout.
- Runtime: pandas, numpy, pyarrow, pydantic 2, PyYAML, Typer, SQLAlchemy 2, psycopg 3, FastAPI, Uvicorn.
- Dev: pytest, ruff, httpx.
- Added only by the card that needs them: `kiteconnect` (T07), `alembic` (T06), `redis` (T11), `boto3` (T13).
- Journal: SQLAlchemy Core tables, PostgreSQL in Compose, SQLite when `TRADEMIND_DATABASE_URL` is unset.
- Bars: Parquet through pyarrow, `data/bars/{interval}/{SYMBOL}.parquet`.
- No other dependency without the owner's approval.

---

## 4. Data contracts

### 4.1 Bars and timeframes

A bars table is a `pandas.DataFrame` for **one symbol and one interval**:

| column | type | meaning |
|---|---|---|
| `ts` | tz-aware `Asia/Kolkata` timestamp | bar **open** time |
| `open`, `high`, `low`, `close` | float64 | prices |
| `volume` | int64 | traded quantity in the bar; `0` for index symbols |
| `oi` | float64, optional | open interest |

Intervals are named `1minute`, `3minute`, `5minute`, `15minute`, `60minute`, `day`.

- **Base interval**: `session.base_interval` in `settings.yaml`, default `1minute`. Only base bars are stored and fed to the engine. A full 1-minute session has 375 bars: 09:15 ... 15:29.
- **Derived intervals** are built from base bars by resampling, with buckets anchored at the session open (a 15-minute bar opens at 09:15, 09:30, ...; a 60-minute bar at 09:15, 10:15, ...). A bucket that cannot reach full length before the session close (for example the 60-minute bucket opening at 15:15) is marked `complete = False` and never shown to strategies.
- **Timeframe is a strategy parameter.** The same rule set can run as several instances on different timeframes, each with its own paper account and scoreboard row. Every instance's timeframe must be a multiple of the base interval.
- Daily bars are built by aggregating base bars per session, `ts` at 00:00 IST of the session date.

Rules:

- Sorted by `ts`, unique `ts`.
- **Missing base bars are normal.** Kite omits a 1-minute candle when nothing traded in that minute. Validation reports the count per session; it is not an error. Derived bars are built from whichever base bars exist; a bucket with no base bars produces no row.
- A date is a trading session if the market symbol has base bars for it. The backtest never consults a holiday list.

### 4.2 Index symbols have no volume

Kite returns `volume = 0` for index symbols (`NIFTY 50`, `NIFTY BANK`). Therefore:

- `Instrument.has_volume` is `False` for indices.
- Session VWAP for a no-volume symbol falls back to the running mean of typical price (`(high+low+close)/3`), exposed under the same column name `vwap`. This is an approximation and is recorded on each trade as `vwap_kind = "avg_price"`.
- Relative-volume features are `NaN` for indices. Every strategy spec says what to do when a volume feature is missing.

### 4.3 Instruments

```python
class Segment(StrEnum):
    EQ_INTRADAY = "EQ_INTRADAY"
    EQ_DELIVERY = "EQ_DELIVERY"
    FUT = "FUT"
    OPT = "OPT"

@dataclass(frozen=True)
class Instrument:
    symbol: str          # e.g. "RELIANCE", "NIFTY 50"
    exchange: str        # "NSE", "NFO"
    kind: str            # "stock" | "index"
    trade_segment: Segment   # segment used to cost paper trades on this symbol
    lot_size: int        # 1 for stocks; index lot size comes from config or Kite instruments
    tick_size: float
    has_volume: bool
```

Lot sizes, tick sizes and expiry dates change by exchange circular. They are **never hardcoded in source**. In phases 0 to 4 they come from `config/settings.yaml`; from T07 they are refreshed from the Kite instruments dump.

### 4.4 How index trades are simulated

Indices cannot be traded directly. Until options are designed (T20):

- Signals are computed on the index spot series.
- Paper trades on an index are simulated **as if on a future tracking the spot price one-to-one**, with `trade_segment = FUT`, the configured lot size, and futures costs. Basis and roll are ignored. Each trade records `sim_kind = "index_as_future"`.
- This is a known approximation. Its main effect is that costs are realistic while fills are slightly optimistic.

### 4.5 Core trading objects

A **strategy instance** is one strategy id running on one timeframe with one parameter set. Its `instance_id` is `"{strategy_id}@{timeframe}"`, for example `orb_momentum@15minute`.

```python
class Side(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"

class ExitReason(StrEnum):
    STOP = "STOP"
    TARGET = "TARGET"
    TIME = "TIME"            # strategy's own time exit
    SQUAREOFF = "SQUAREOFF"  # global end-of-day exit
    RULE = "RULE"            # strategy-specific exit rule (swing only)

@dataclass(frozen=True)
class Signal:
    strategy_id: str
    strategy_version: str
    timeframe: str            # e.g. "5minute"
    symbol: str
    ts: pd.Timestamp          # open time of the timeframe bar whose close produced the signal
    side: Side
    stop: float
    target: float | None
    time_exit: datetime.time | None   # exit at the open of the first base bar with ts.time() >= time_exit
    features: dict[str, float | str | bool | None]   # values the strategy used, for the journal
    reason: str               # short human-readable explanation

    @property
    def instance_id(self) -> str: ...   # f"{strategy_id}@{timeframe}"

@dataclass
class Trade:
    trade_id: str
    run_id: str
    strategy_id: str
    strategy_version: str
    timeframe: str
    instance_id: str
    symbol: str
    side: Side
    qty: int
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp    # open time of the base bar where the entry filled
    entry_price: float        # after slippage
    exit_ts: pd.Timestamp
    exit_price: float         # after slippage
    exit_reason: ExitReason
    stop: float
    target: float | None
    risk_per_unit: float      # abs(entry_price - stop)
    gross_pnl: float
    costs: float
    net_pnl: float
    r_multiple: float         # net_pnl / (qty * risk_per_unit)
    mfe_r: float              # max favourable excursion in R while open, from base bar highs/lows
    mae_r: float              # max adverse excursion in R (positive number)
    post_exit_mfe_r: float | None        # trap diagnostic, section 9.5; None unless exit_reason is STOP
    target_hit_after_stop: bool | None   # trap diagnostic, section 9.5; None unless exit_reason is STOP and a target exists
    features: dict
    context: dict
```

---

## 5. Engine semantics (backtest and live paper are identical)

Global session settings (`config/settings.yaml`):

- `session_open: 09:15`, `session_close: 15:30`, `base_interval: 1minute`
- `last_entry_time: 14:45` (no new entries from this base bar on, unless a strategy sets `allow_late_entry`)
- `squareoff_time: 15:20` (all intraday positions exit at the open of the 15:20 base bar)

### 5.1 Loop

The engine clock ticks on the **base grid**. Strategies are called only when a bar of **their own timeframe** has just closed.

```
for each session date D:
    build DayContext for every symbol (previous close, gap, daily features)
    call strategy.on_day_start(D) for every strategy instance
    for each base bar time T in the base grid of D:
        for each symbol S with a base bar at T:
            1. broker.on_bar_open(S, bar)    # fill pending entries, gap exits, time exits, square-off
            2. broker.on_bar_range(S, bar)   # stop/target checks using the base bar's high/low
        if T + base == session_open + selector.or_minutes:
            select stocks in play and set opening-range tags (STRATEGIES A.3)
        for each strategy instance X whose timeframe bar closes at T + base:
            for each symbol S in scope for X that has that completed timeframe bar:
                3. view = BarView(S, X.timeframe, completed timeframe bars of D, base bars of D up to T)
                4. signals = X.on_bar(view)
                5. for each signal: decision = risk.evaluate(signal, ...)
                   journal the signal with approved/rejected and reason
                   if approved: broker.queue_entry(order)   # fills at the next base bar's open
    cancel pending entries, close leftovers, compute trap diagnostics (9.5)
    journal all trades closed on D, and the day's context tags
```

A timeframe bar that opens at `T0` with length `L` closes at `T0 + L`. It "closes at `T + base`" when `T0 + L == T + base`. Only buckets marked `complete` are delivered.

Example with a 1-minute base: the 5-minute bar 09:30 closes at 09:35, so a `5minute` instance is called after base bar 09:34 is processed, and an approved entry fills at the open of base bar 09:35.

### 5.2 Fill rules

"Bar" in this section means a **base bar**. Let `slip` be the per-side slippage fraction for the instrument's segment (`costs.yaml`).

- **Entry**: at the **open of the next base bar** after the signal's timeframe bar closes. Long fills at `open * (1 + slip)`, short at `open * (1 - slip)`.
- **Entry cancelled** (journalled as rejected, reason in brackets) when:
  - the symbol has no later base bar in the session (`no_next_bar`);
  - the fill bar's time is at or after `last_entry_time` and the strategy does not allow late entry (`after_last_entry`);
  - the fill bar's time is at or after `squareoff_time`, even for strategies that allow late entry (`after_last_entry`);
  - the fill bar's open is already beyond the stop: long with `open <= stop`, short with `open >= stop` (`entry_through_stop`);
  - a target exists and the open is already beyond it: long with `open >= target`, short with `open <= target` (`entry_through_target`).
- A pending entry waits for the symbol's next base bar, however many minutes later that is.
- **Stop and target apply from the entry bar onward**, including the entry bar itself.
- **Gap exit**: if a bar opens beyond the stop, exit at that open with reason `STOP`. If it opens beyond the target, exit at that open with reason `TARGET`.
- **Order within a base bar**: exits at the open first, then pending entries, then intrabar stop/target (including for a position filled on this bar). When several at-open exits apply, the reason is the first of `STOP`, `TARGET`, `TIME`, `SQUAREOFF`; the price is the same open.
- **Intrabar**: for a long, `low <= stop` exits at `stop`; `high >= target` exits at `target`. Mirrored for shorts.
- **Both in one bar**: if the same base bar touches both stop and target, the exit is `STOP`. This is deliberately conservative, and rare on 1-minute bars.
- **Time exit**: at the open of the first bar with `ts.time() >= signal.time_exit`, reason `TIME`.
- **Square-off**: at the open of the first bar with `ts.time() >= squareoff_time`, reason `SQUAREOFF`. If the symbol's data ends earlier, exit at its last bar's close with reason `SQUAREOFF`.
- **Exit slippage**: sells fill at `price * (1 - slip)`, buys (short covers) at `price * (1 + slip)`.
- Prices are not rounded to tick size in v1.

### 5.3 Shadow accounts

Each strategy **instance** has its own independent paper account. Instances never block each other, including two timeframes of the same strategy. Limits (section 6) are applied per instance.

### 5.4 No-lookahead guarantees

- `BarView.bars` contains only **completed** timeframe bars whose close time is `<= T + base`. `BarView.base` contains only base bars with `ts <= T`.
- Feature columns must be **causal**: the value at row `i` depends only on rows `<= i` (and earlier sessions).
- Higher-timeframe values attached to a base row (for example `trend_60m`) come from the last higher-timeframe bar that had **already closed** by that base row's close.
- Test required for every feature: compute on the full data, compute on the data truncated at row `i`, values at rows `<= i` must be equal.
- End-of-day context tags (for example `day_type`) and trap diagnostics are stored for analysis only and are never visible through `BarView`.

---

## 6. Risk and sizing

Settings in `config/settings.yaml` under `risk:` (defaults shown):

| key | default | meaning |
|---|---|---|
| `risk_per_trade_inr` | 1000 | 1R. Loss if the stop is hit, before costs |
| `max_notional_inr` | 500000 | cap on `qty * entry price` |
| `segment_overrides` | `FUT: {risk_per_trade_inr: 7500, max_notional_inr: 2500000}` | per-segment replacements for the two values above |
| `max_trades_per_day` | 3 | per strategy instance, across symbols; counts approvals |
| `max_open_positions` | 2 | per strategy instance, open plus pending |
| `max_consecutive_losses` | 2 | per strategy instance per day, then stop for the day |
| `daily_loss_limit_r` | -3.0 | per strategy instance per day, on closed trades |
| `kill_switch` | false | when true, every signal is rejected |

One position per (instance, symbol) is always enforced. Why the override exists: one Nifty futures lot is about Rs 18 lakh of notional, so with 1R = Rs 1,000 and a Rs 5 lakh cap no index trade could ever be sized. At Rs 7,500 per R an index trade fits when its stop is within about 100 Nifty points. These are placeholders for the owner to set.

Sizing at approval time, using the close of the signal's timeframe bar as the expected entry:

```
risk_per_unit_est = abs(signal_bar_close - signal.stop)
risk_inr, max_notional = limits for the instrument's segment (after overrides)
qty = floor(risk_inr / risk_per_unit_est)
qty = floor(qty / lot_size) * lot_size
qty = min(qty, floor(floor(max_notional / signal_bar_close) / lot_size) * lot_size)
reject "qty_too_small" if qty < lot_size
```

Check order, first failure wins: `kill_switch`; `invalid_input` (non-finite or non-positive price or stop, stop on the wrong side of the price, target on the wrong side); `zero_risk`; `position_exists`; `max_open_positions`; `max_trades_per_day`; `consecutive_losses`; `daily_loss_limit`; then sizing and `qty_too_small`.

`r_multiple` on the closed trade uses the actual entry fill, as defined in section 4.5.

Rejection reasons are a closed set (`RejectReason`); add new ones only with a spec change:
`kill_switch`, `invalid_input`, `qty_too_small`, `zero_risk`, `max_trades_per_day`, `max_open_positions`, `position_exists`, `consecutive_losses`, `daily_loss_limit`, `no_next_bar`, `after_last_entry`, `entry_through_stop`, `entry_through_target`.

---

## 7. Costs

Rates are in `config/costs.yaml`. Values below were read from Zerodha's charges page on 2026-11-14 and **must be re-checked** whenever going near live trading. They change with budgets and exchange circulars.

| | EQ_INTRADAY | EQ_DELIVERY | FUT | OPT (on premium) |
|---|---|---|---|---|
| Brokerage per executed order | min(0.03%, Rs 20) | 0 | min(0.03%, Rs 20) | flat Rs 20 |
| STT | 0.025% sell | 0.1% buy and sell | 0.05% sell | 0.15% sell |
| NSE transaction charge | 0.00307% | 0.00307% | 0.00183% | 0.03553% |
| SEBI charge | Rs 10 per crore | same | same | same |
| Stamp duty (buy side) | 0.003% | 0.015% | 0.002% | 0.003% |
| GST | 18% of (brokerage + SEBI + transaction) | same | same | same |

Formula for a round trip with buy value `B` and sell value `S` (two orders):

```
brokerage = brk(B) + brk(S)
stt       = B * stt_buy + S * stt_sell
txn       = (B + S) * txn_rate
sebi      = (B + S) * 10 / 1e7
stamp     = B * stamp_buy
gst       = 0.18 * (brokerage + sebi + txn)
total     = brokerage + stt + txn + sebi + stamp + gst
```

No rounding of individual components in v1.

Test vectors (must pass to 4 decimal places):

| segment | buy | sell | brokerage | stt | txn | sebi | stamp | gst | total |
|---|---|---|---|---|---|---|---|---|---|
| EQ_INTRADAY | 100 @ 1000 | 100 @ 1010 | 40.0000 | 25.2500 | 6.1707 | 0.2010 | 3.0000 | 8.3469 | 82.9686 |
| EQ_INTRADAY | 10 @ 500 | 10 @ 505 | 3.0150 | 1.2625 | 0.3085 | 0.0100 | 0.1500 | 0.6000 | 5.3461 |
| FUT | 75 @ 24000 | 75 @ 24050 | 40.0000 | 901.8750 | 65.9486 | 3.6037 | 36.0000 | 19.7194 | 1067.1468 |
| OPT | 75 @ 120 | 75 @ 150 | 40.0000 | 16.8750 | 7.1948 | 0.0203 | 0.2700 | 8.4987 | 72.8588 |
| EQ_DELIVERY | 50 @ 2000 | 50 @ 2200 | 0.0000 | 210.0000 | 6.4470 | 0.2100 | 15.0000 | 1.1983 | 232.8553 |

Note the futures row: one index lot costs about Rs 1,067 per round trip, roughly 14 index points. Any index setup must clear that before it earns anything.

Slippage per side (`costs.yaml`, in basis points of price): `EQ_INTRADAY: 3`, `EQ_DELIVERY: 5`, `FUT: 1.5`, `OPT: 50`. These are starting guesses to be calibrated against live paper fills in phase 5.

---

## 8. Journal (PostgreSQL in Compose, SQLite locally)

Tables are SQLAlchemy Core definitions in `database/models.py`. Timestamps are stored in UTC and read back as Asia/Kolkata. JSON columns hold features and tags; NaN is stored as null.

| table | one row per | key columns |
|---|---|---|
| `runs` | backtest or live session | `run_id`, `mode` (`backtest`/`paper`), `data_split` (`research`/`holdout`/`live`), `period_start`, `period_end`, `config_hash`, `git_sha`, `source`, `instances`, `started_at`, `finished_at`, `status`, `n_signals`, `n_trades` |
| `signals` | signal emitted | `signal_id`, `run_id`, strategy, `timeframe`, `instance_id`, symbol, `ts`, side, stop, target, `ref_price`, `approved`, `reject_reason`, `qty`, `reason`, `features` |
| `trades` | closed round trip | all `Trade` fields, including trap diagnostics; `features`, `context` |
| `day_context` | (run, date, symbol) | `tags`, including end-of-day tags |
| `trials` | backtest evaluation of one strategy instance | `trial_id`, `created_at`, strategy, version, `timeframe`, `params_hash`, `data_split`, period, `n_trades`, `expectancy_r`, `run_id` |
| `judge_scores` | LLM judgement of a signal (T14, not created yet) | `signal_id`, model, rubric version, score, `reasons_json` |

`config_hash` is the SHA-256 of the three YAML config files' contents. `params_hash` is the SHA-256 of the strategy's parameters serialised as sorted JSON.

---

## 9. Analytics and validation

### 9.1 Metrics (per strategy instance, optionally per context value)

- `n_trades`
- `win_rate` = share of trades with `net_pnl > 0`
- `avg_win_r`, `avg_loss_r`
- `expectancy_r` = mean of `r_multiple`
- `profit_factor` = sum of positive `net_pnl` / abs(sum of negative `net_pnl`); `inf` if no losses
- `max_drawdown_r` = largest peak-to-trough fall of the cumulative `r_multiple` curve, trades ordered by `exit_ts`
- `total_net_pnl`, `total_costs`, `cost_share` = `total_costs / sum(abs(gross_pnl))`
- `false_breakout_rate` = share of trades with `exit_reason == STOP` and `mfe_r < 0.5`
- `stopped_then_right_rate` = among trades with `exit_reason == STOP` and a target, the share with `target_hit_after_stop == True` (section 9.5); `NaN` if there are none
- `insufficient_sample` = `n_trades < analytics.min_trades` (default 100)

### 9.2 Data split

- `validation.holdout_start` in `settings.yaml` is a date. Data before it is **research**; data from it onward is **holdout**.
- Normal backtests refuse to read holdout dates.
- `trademind validate` (T05) is the only command that reads holdout data. Every use is written to `trials` with `data_split = holdout`.

### 9.3 Promotion gate (candidate to paper)

The gate is evaluated per strategy instance (strategy id, version, timeframe). An instance passes when all hold:

1. Research: `n_trades >= 100`.
2. Research: the lower bound of a bootstrap confidence interval for `expectancy_r` is above 0. Confidence level is `1 - 0.05 / k`, where `k` is the number of research trials logged for that `strategy_id` across all versions, parameter sets **and timeframes** (Bonferroni correction). Adding a timeframe therefore raises the bar for every instance of that strategy. 10,000 resamples, fixed seed.
3. Research: `max_drawdown_r <= 15`.
4. Holdout: `n_trades >= 30` and `expectancy_r > 0`.
5. The holdout was evaluated at most twice for this strategy instance.

### 9.4 Paper to live gate

Out of scope to implement, recorded here so nobody improvises it later: at least 60 live paper trades, live paper `expectancy_r` within the research confidence interval, the owner's written sign-off, and the compliance items in section 10.

### 9.5 Trap diagnostics

"Traps" are moves that run just far enough to hit stops placed at obvious levels (the day's high or low, the opening range edge, the previous day's extremes) and then reverse. The lab treats this as something to measure and to trade, not as folklore.

**Measured on every stopped trade.** For a trade with `exit_reason == STOP`, using the symbol's base bars after `exit_ts` up to (not including) the square-off bar:

- `post_exit_mfe_r`: for a long, `(max(high) - entry_price) / risk_per_unit`; for a short, `(entry_price - min(low)) / risk_per_unit`. May be negative. `None` if there are no such bars.
- `target_hit_after_stop`: `True` if a target exists and price reached it in that window (long: `max(high) >= target`; short: `min(low) <= target`), else `False`. `None` if the trade has no target or there are no such bars.

`stopped_then_right_rate` (9.1) then answers "how often was the idea right and only the stop wrong?" for each instance and context. A high value points at stop placement, not at the setup.

**What the lab can do about it** (each is a spec change, a new version and a logged trial; none is on by default):

- `stop_buffer_atr`: place level-based stops a fraction of ATR beyond the level instead of exactly on it (STRATEGIES Part C, shared rules). Default `0.0`.
- Trade the trap: `failed_orb_fade` (STRATEGIES C.2) and `sweep_reversal` (STRATEGIES C.6) enter **after** the stop run fails.
- Retest entries (STRATEGIES Part E) are planned but not specified.

A low win rate alone is not a trap problem. A setup with a 2R target can be right one time in three and still be worth trading; expectancy after costs is the measure.

---

## 10. Guardrails

- **No order placement code.** The Kite integration uses read-only endpoints: login/session, instruments, historical candles, quotes, and the tick WebSocket. `tests/test_no_order_code.py` scans `src/` and fails if `place_order`, `modify_order`, `cancel_order`, `place_gtt` or the `/orders` path appear.
- **Secrets** live in `.env` and `data/`, both gitignored. `.env.example` lists names only. Never commit a real value, whatever the repository's visibility.
- **Network exposure**: Compose binds Postgres, the API and Redis to 127.0.0.1. The API is read-only and every endpoint except `/health` needs `TRADEMIND_API_TOKEN`.
- **Execution mode**: config accepts only `PAPER`. Other modes fail validation.
- **Kite login is manual each day**: the CLI prints the login URL, the owner pastes back the `request_token`. No stored password, no automated TOTP.
- **Kite rate limits** to respect: historical candles 3 requests/second, quotes 1 request/second, other endpoints 10 requests/second; up to 3 WebSocket connections with 3,000 instruments each.
- **Historical request windows** (max days per request): minute 60, 5minute 100, 15minute 200, 60minute 400, day 2000.
- **Going live later** needs, at minimum: a whitelisted static IP for API orders, staying under 10 orders per second, a fresh check of all charges, and the gate in 9.4. None of that is built here.

---

## 11. Research layer (T13-T16, summary)

- **Daily post-mortem** (after close): input is the day's trades, rejected signals and context; output is a short written review and rule-compliance notes.
- **Setup judge, shadow mode**: for each approved signal, the LLM scores a fixed rubric (news agrees with direction, event risk today, market agrees) and returns structured JSON. Scores are stored in `judge_scores` and have **no effect on trading** while `judge.veto_enabled: false`. After 200+ judged trades, compare outcomes by score to decide whether to give it veto power.
- **Weekly review**: reads the scoreboard and losing-trade clusters, proposes at most two hypotheses as parameter changes or new filter specs. Proposals go to `docs/hypotheses/` as files. Nothing is auto-merged; the owner approves, then the change is backtested and logged as a trial.
- **News**: headline ingestion and tagging per stock. Source is an open decision.
- The LLM client is an interface with Bedrock and Anthropic API implementations, model chosen in config.

---

## 12. Open decisions for the owner

1. **Repository visibility.** Owner asked for `Object_de` to be private; it must be switched in GitHub settings before strategy code is pushed.
2. **Stock universe.** Starter list in `settings.yaml` is ten liquid large caps; edit freely.
3. **Paper risk unit.** 1R = Rs 1,000 for stocks, Rs 7,500 for index futures (placeholders).
4. **Kite paid plan** (Rs 500/month) is needed from T07. Nothing built so far needs it.
5. **LLM provider and model** for phase 6: Bedrock or Anthropic API; Sonnet-class for daily work.
6. **News source** for phase 6.
7. **Index instrument for paper trading**: simulated future first (section 4.4), options after T20.

---

## 13. What success looks like

- Now: `trademind backtest` runs every enabled strategy instance over a year of 1-minute data for the 12-symbol universe (about 30 seconds for four instances) and prints a scoreboard net of costs.
- After T01-T05: six setups, and `trademind validate` enforces the promotion gate.
- After T07-T10: the live paper runner trades the same rules during market hours and sends a Telegram summary at close.
- An honest result is a valid result. If no setup passes the gate, the lab has done its job by showing that before any money was risked.
