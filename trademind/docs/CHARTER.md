# TRADEMIND charter

One page. It says what this project is trying to learn, by when, and what happens if the answer is no. Written 2026-11-23 after the full review (`reviews/2026-11-23.md`). The owner may change the dates; record any change in `DECISIONS.md`.

## The question

Does any rule-based NSE strategy in this repo earn **more than its costs**, on data it was not tuned on, with fills close to what a real broker would give?

Paper only, always. Nothing here places an order. A "yes" means "worth longer forward testing", not "trade real money".

## Why it might be "no"

These come from the review; they are the reasons to expect failure, not just to hope against:

- **Costs.** Zerodha charges plus modelled slippage cost about 0.14R to 0.7R per intraday stock trade. The gate needs roughly 0.25R to 0.3R net expectancy. Classic breakout, fade and momentum patterns on a dozen mega caps are unlikely to clear that.
- **Sample size.** One research year and 12 symbols give about 150 trades per strategy.
- **Hindsight.** The stock list is today's large caps, chosen after the fact.
- **Fill model.** Paper fills use the same fixed slippage as the backtest. The bid/ask capture added in this review is what will show how optimistic that model is.

## Phases and dates

| By | Phase | Pass | If it fails |
|---|---|---|---|
| 2026-12-15 | **Real-data research.** Download the data, run `TESTING.md` steps 1 to 3, and read `gross_expectancy_r` against `cost_per_trade_r` for every instance. | At least one instance has gross expectancy above **2 x its cost per trade**, with at least 100 trades. | Stop intraday stock work. Go straight to swing (T18), which has a lower cost per R. |
| 2027-01-15 | **Holdout.** Run `validate` once per surviving instance (`TESTING.md` step 4), and record each verdict in `DECISIONS.md`. | The promotion gate passes. | Drop that instance. If none is left, go to swing (T18). |
| 2027-03-31 | **Forward paper.** Run live paper days on the laptop, then the server, after the holdout window. | At least 40 completed paper days, all four of: expectancy > 0 after costs, execution drift (paper check section 4) below **0.05R** per trade, max drawdown within the research figure, and paper check section 2 PASS on every day. | Stop and write up what was learned. |

**Decision date: 2027-03-31.** On that day the owner chooses one of three outcomes:
- **Continue:** a longer forward test, with more symbols, and swing alongside intraday.
- **Pivot:** swing or positional strategies only (T18, T21).
- **Stop.**

## Rules that keep the answer honest

- **Holdout:** fixed at 2026-05-01..2026-10-31, with 2 looks per strategy, counted in `ledger/` in git (D29).
- **No tuning:** parameters change only through a spec change with a new version. A new version gets no new holdout looks.
- **Bonferroni:** counts every distinct hypothesis ever tested on real data, across all strategies.
- **Paper days:** only completed `done` days count. Stopped, crashed and superseded runs do not.
- **AI review:** the weekly AI review stays paused until something passes the gate. AI suggestions never change rules directly.

## Out of scope until something passes

These wait: news (T16), options and expiry (T20), the AI setup judge (T14), and the Redis event bus (T11, dropped). Real-money execution is out of scope entirely.

## Budget

The ceiling is **Rs 10,000 a month all-in.**
- **Server:** laptop first. The AWS server starts only after the laptop phase passes (`TESTING.md` step 5).
- **Claude plan:** Claude Max at most for an intensive month, then Pro.
- **Agent Bedrock fallback:** off.
