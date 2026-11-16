# T09 Live paper runner: design (built)

Status: implemented 2026-11-17 in `services/execution/live_paper.py` and `kite_stream.py`.

## Goal
Trade the same rules live, on paper, and make the same decisions the backtest would make on the same bars.

## How
- **One engine path.** `EngineSession` runs a day as `begin_day`, `step(g)` for each base minute, then `finish_day`. The backtest calls `run_day`, which is exactly that loop; the live runner calls `step(g)` as each minute completes.
- **Ticks to bars.** `BarAggregator` builds 1-minute bars from Kite full-mode ticks, using the exchange timestamp and differencing cumulative day volume. Index ticks carry no volume.
- **When a minute is processed.** Minute g is processed `grace` seconds (default 5) after it ends. Ticks that arrive later are counted and dropped.
- **Features.** At every timeframe close and at the selection minute, features are rebuilt from the last 30 sessions plus today's bars, while day context (daily trend, volatility regime) uses the full stored history. Every feature is causal and has a window shorter than 30 sessions, so the values equal the backtest's. Between closes only raw bars are refreshed, since only the paper broker reads them.
- **Late start.** If started after 09:15, today's completed minutes are fetched from Kite historical candles and fed in first; the aggregator is seeded with the cumulative volume so the next live bar's volume is right.
- **Close.** At 15:30 the journal is written (`mode=paper`, `data_split=live`), today's bars are appended to the Parquet store so tomorrow has history, and a Telegram summary is sent.
- **Safety.** Fills are simulated by `PaperBroker`. The Kite client is wrapped in `ReadOnlyClient`, whose allowlist has no order methods.

## Proof
`tests/test_live.py` replays a synthetic day as ticks (open, high, low, close per minute) through the runner and requires the same trades (entry, exit, prices, P&L, R, MFE/MAE, trap diagnostics) and the same signals (including rejections) as `run_backtest`. A second test starts late with a 100-minute backfill and gets the same trades.

## Known limits
- The journal is written at the close. If the process dies mid-day, that day's paper trades are lost (bars can be re-downloaded). Incremental journalling is a later improvement.
- The minute in progress when a late start happens is built from ticks only after the start, so its open, high and low can be incomplete.
- Kite's access token expires daily: `trademind login` each morning before `trademind paper run`. There is no automated login, by design.
