# Decisions log

The owner asked for the build to be completed end to end, with design decisions taken in the project's best interest. Each decision is recorded here with its reason, so any of them can be revisited.

| # | Date | Decision | Why | Revisit when |
|---|---|---|---|---|
| D1 | 2026-11-16 | Research core before live plumbing | Learn whether any setup has an edge before building infrastructure around it | - |
| D2 | 2026-11-16 | 1-minute base data; every timeframe derived from it | One stored resolution, accurate fills, timeframe becomes a testable parameter | - |
| D3 | 2026-11-16 | Journal on PostgreSQL in Compose, SQLite locally and in tests | Production-grade where it runs, zero setup on a laptop | - |
| D4 | 2026-11-16 | Index trades simulated as a future tracking spot; options later | Realistic costs now; options need data that must be archived first | Options design (T20) |
| D5 | 2026-11-16 | Index futures risk unit Rs 7,500 per R, notional cap Rs 25 lakh | One Nifty lot is ~Rs 18 lakh notional; Rs 1,000 per R could never size it | Owner sets real capital |
| D6 | 2026-11-17 | Kite access is read-only by construction (allowlisted client) | Makes accidental order calls impossible, not just untested | Live execution gate (Phase 14) |
| D7 | 2026-11-17 | Manual daily Kite login, no stored password or TOTP automation | Credentials never sit on a server | - |
| D8 | 2026-11-17 | Live runner reuses the backtest engine step by step; parity proven by replay | Paper results then mean the same as backtest results | - |
| D9 | 2026-11-17 | Live journal written at the close, not continuously | Simpler and parity-safe; a mid-day crash loses only that day's paper trades | After first month of live paper |
| D10 | 2026-11-17 | Live features from the last 30 sessions; day context from full history | Same values as the backtest at a fraction of the compute | - |
| D11 | 2026-11-17 | All six intraday strategies enabled on 5 and 15 minutes (first-half-hour: 5 only) | More evidence per day; the trial count makes the gate stricter accordingly | Gate results |
| D12 | 2026-11-17 | Promotion gate: bootstrap lower bound with Bonferroni over research trials, max two holdout looks per version | Many variants must not manufacture a false winner | - |
| D13 | 2026-11-17 | Synthetic volume rises with the size of each minute's move | Exercises relative-volume features; still no edge by construction | - |
| D14 | 2026-11-17 | LLM: AWS Bedrock, Haiku-class for routine tagging, Sonnet-class for reviews | Matches the blueprint and the owner's AWS stack | Cost or quality data |
| D15 | 2026-11-17 | News: free sources first (RSS feeds, NSE corporate announcements) | No cost until news proves useful in the scoreboard | If news tags show value |
| D16 | 2026-11-17 | Daily Kite login through Telegram: the bot sends the link, the owner pastes back the redirect URL | Works from a phone with no public endpoint on the server | - |
| D17 | 2026-11-17 | AWS: one t4g.medium in ap-south-1, default VPC, no inbound ports, SSM only, Elastic IP, encrypted EBS/S3, budget alert | Blueprint section 14 at the smallest sensible size | Load or reliability data |
| D18 | 2026-11-17 | Scheduling with systemd timers on the instance (08:40 weekdays, backup 20:00) | Fewer moving parts than EventBridge plus SSM Run Command | - |
| D19 | 2026-11-17 | Research layer off by default; enabled by filling Bedrock model ids and prices in settings.yaml | Model ids differ by account and region; no guessed ids in config | - |
| D20 | 2026-11-17 | Hard monthly LLM budget (default $15) enforced in code before every call; every call's tokens and cost journalled | Cost cannot run away unattended | Actual spend |
| D21 | 2026-11-17 | Weekly review proposals capped at two in code and written to files only | Keeps the trial count honest; the owner decides | - |
| D22 | 2026-11-17 | Setup judge (T14) deferred until a news feed exists | With only price features the judge would repeat what the rules already know | After T16 |
| D23 | 2026-11-17 | Market regime: rule-based label from the market symbol's session-start trend and volatility | Explainable, no lookahead; becomes a scoreboard dimension (`--by market_regime`) | After enough paper trades per regime |
| D24 | 2026-11-17 | Dashboard as one static page served by the API, not a separate Next.js app | No build chain or extra service; the token stays in the browser session; reached through the SSM tunnel | If several people need access |

## Findings worth knowing

- **Costs dominate short holds.** One Nifty futures round trip costs about Rs 1,067 (about 14 points). `first_half_hour_momentum`, which holds about 20 minutes, loses about 37% of its gross moves to costs on synthetic data.
- **`intraday_contraction` almost never triggers on random-walk data.** The tight-then-breakout sequence is rare without real market structure. The rules are proven by unit tests; real data will show how often it fires. Parameters were not loosened.
