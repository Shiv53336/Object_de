# Strategy and Feature Specifications

Status: v2, 2026-11-15. Implemented: `orb_momentum` (C.1) and `sweep_reversal` (C.6). Changes in v2: every intraday rule is written for any timeframe; higher-timeframe trend features; optional stop buffer; new trap setup `sweep_reversal`.

These are **hypotheses to test**, written precisely enough to code and to falsify. None is known to be profitable on Indian markets after costs. Most of the supporting research is on US data.

Implement exactly what is written. If a rule is ambiguous, stop and ask; do not pick an interpretation silently. Any change to a rule requires a new `version` string.

Conventions used below:

- Each strategy **instance** runs on one timeframe (`5minute`, `15minute`, ...). "Bars" always means **completed bars of the instance's timeframe**, unless "base bar" is written. `tf` is the timeframe length in minutes.
- "Bar T" is the timeframe bar that **opens** at time T. It closes at T + tf. A signal "at bar T" is computed at that close and fills at the open of the next **base** bar (PLAN 5.2).
- Time windows are written `[start, end)` on the bar's **open** time.
- `close_time(T) = T + tf`.
- `prev` means the previous completed bar of the same timeframe in the same session.
- All percentages are in percent units (1.0 means 1%).
- "Stocks" are instruments with `kind == "stock"`, "indices" have `kind == "index"`.

---

## Part A. Features

All features are causal (PLAN 5.4).

### A.1 Base columns (computed on base bars, `features/indicators.py` and `features/htf.py`)

| column | definition | missing when |
|---|---|---|
| `vwap` | Per session: `cumsum(tp * volume) / cumsum(volume)` with `tp = (high + low + close) / 3`. If the instrument has no volume, or cumulative volume is 0: expanding mean of `tp` within the session. | never |
| `day_high`, `day_low` | Expanding max of `high` / min of `low` within the session, including the current bar. | never |
| `trend_15m`, `trend_60m` | Higher-timeframe trend label, see A.7. | never (value may be `unknown`) |

When base bars are resampled to a timeframe, these columns take the value on the **last base bar** of each bucket.

### A.2 Timeframe columns (computed on the completed bars of one timeframe)

| column | definition | missing when |
|---|---|---|
| `atr14` | True range `tr = max(high - low, abs(high - prev_bar_close), abs(low - prev_bar_close))`, where `prev_bar_close` is the previous bar's close **across session boundaries**; the very first bar of the dataset uses `high - low`. `atr14` is the simple rolling mean of `tr` over 14 bars. | first 13 bars of the dataset |
| `tod_rvol` | `volume / mean(volume of the bar opening at the same time of day over the previous 20 sessions)`. Needs at least 10 previous sessions having that bar. | no-volume instrument, fewer than 10 sessions, or mean is 0 |

Timeframe frames contain only complete buckets (PLAN 4.1).

### A.3 Opening range (`BarView.opening_range(minutes)`)

Computed from **base** bars in the window `[session_open, session_open + minutes)`:

- `high` = max high, `low` = min low, `open` = open of the first base bar in the window, `close` = close of the last base bar in the window, `volume` = sum of volume.
- `or_end = session_open + minutes`.
- Returns `None` until the clock reaches `or_end` (that is, while `close_time` of the current bar is before `or_end`), and `None` if the window contains no base bars.

### A.4 Day context (`DayContext`, one per symbol per session)

Daily bars are built by aggregating base bars per session. Everything here uses **previous** sessions only, except `gap_pct` (uses today's first open) and the two fields set at selection time.

| field | definition | known at |
|---|---|---|
| `prev_close` | Close of the previous session. `None` if there is none. | session start |
| `prev_day_high`, `prev_day_low` | High and low of the previous session. `None` if there is none. | session start |
| `gap_pct` | `(open of today's first base bar - prev_close) / prev_close * 100`. `None` if `prev_close` is `None`. | first bar |
| `daily_atr_pct` | Daily true range uses the prior session's close. `daily_atr_pct = mean(TR of previous 14 sessions) / prev_close * 100`. `None` if fewer than 15 previous sessions exist. | session start |
| `daily_trend` | With `sma20` and `sma50` of the previous sessions' closes: `up` if `prev_close > sma20` and `sma20 > sma50`; `down` if `prev_close < sma20` and `sma20 < sma50`; otherwise `flat`; `unknown` if fewer than 50 previous sessions. | session start |
| `or_rvol` | See A.5. `None` before selection time and for no-volume instruments. | selection time |
| `in_play` | See A.5. Always `True` for indices. | selection time |

### A.5 Stocks in play (`features/selector.py`)

Selection time is `session_open + selector.or_minutes` (default 15 minutes, so 09:30). At that moment, for every stock:

- `or_rvol = (opening range volume over selector.or_minutes) / mean(the same volume over the previous 20 sessions)`. Needs at least 10 previous sessions and a non-zero mean; otherwise `None`.

Then:

1. Keep stocks with `or_rvol >= selector.min_or_rvol` (default 1.5).
2. Sort by `or_rvol` descending, ties broken by symbol ascending.
3. The first `selector.top_n` (default 5) are in play for the rest of the session.

Before selection time no stock is in play. Phase 6 adds a news flag as an additional way in; not in v1.

### A.6 Market reference

`settings.market_symbol` (default `"NIFTY 50"`). `BarView.market` is the BarView of that symbol **in the same timeframe** at the same bar, or `None` if that bar is missing. `market_above_vwap = market.close > market.vwap` on the current bar.

### A.7 Higher-timeframe trend (`features/htf.py`)

For `H` in `{15, 60}` minutes, build complete `H`-minute bars over all loaded history and label each bar `j` (0-based over the whole dataset):

- `sma20[j]` = mean of the last 20 closes ending at `j`, continuous across sessions.
- `unknown` if `j < 24`.
- `up` if `close[j] > sma20[j]` and `sma20[j] > sma20[j-5]`.
- `down` if `close[j] < sma20[j]` and `sma20[j] < sma20[j-5]`.
- otherwise `flat`.

The value on a base row is the label of the **last `H`-minute bar that had already closed** by that base row's close time; `unknown` if there is none.

In v1 these labels and `daily_trend` are **logged, not used as filters**. Whether trading with the higher timeframe helps is a question for the scoreboard; turning it into a filter is a later spec change.

---

## Part B. Context tags (`features/context.py`)

Stored in `day_context.tags_json` per (date, symbol), and copied into each trade's `context` together with per-trade tags. Tags marked EOD are for analysis only and are never available to strategies.

| tag | values | definition | known at |
|---|---|---|---|
| `gap_bucket` | `gap_up`, `gap_down`, `flat`, `unknown` | `gap_pct > 0.4` up; `< -0.4` down; otherwise flat; `unknown` if `gap_pct` is `None` | first bar |
| `daily_trend` | `up`, `down`, `flat`, `unknown` | A.4 | session start |
| `vol_regime` | `low`, `normal`, `high`, `unknown` | ratio of `daily_atr_pct` to the median of its previous 100 sessions (need at least 30): `< 0.8` low, `> 1.2` high, else normal | session start |
| `is_expiry_day` | `true`, `false`, `unknown` | date listed in `config/expiries.yaml` under the symbol's key (`"NIFTY 50"`, `"NIFTY BANK"`, or `"STOCKS"` for all stocks); `unknown` if the file has no dates for that key in that calendar year | session start |
| `or_width_pct` | number | for the opening range of `selector.or_minutes`: `(high - low) / ((high + low) / 2) * 100` | selection time |
| `or_width_bucket` | `narrow`, `normal`, `wide`, `unknown` | ratio of today's `or_width_pct` to the median of the previous 20 sessions (need at least 10): `< 0.7` narrow, `> 1.3` wide, else normal | selection time |
| `day_type` (EOD) | `trend_up`, `trend_down`, `range`, `mixed`, `flat` | session `range = high - low`; `flat` if 0. `ratio = abs(close - open) / range`, `close_pos = (close - low) / range`. `trend_up` if `ratio >= 0.6` and `close_pos >= 0.75`; `trend_down` if `ratio >= 0.6` and `close_pos <= 0.25`; `range` if `ratio <= 0.3`; else `mixed` | end of day |
| `day_range_pct` (EOD) | number | `(high - low) / open * 100` for the session | end of day |

Per-trade tags (added when the trade is journalled):

| tag | values | definition |
|---|---|---|
| `timeframe` | `5minute`, `15minute`, ... | the instance's timeframe |
| `time_bucket` | `open`, `morning`, `midday`, `afternoon` | by entry time: `[09:15, 10:00)`, `[10:00, 11:30)`, `[11:30, 13:30)`, `[13:30, 15:30)` |
| `market_trend_at_entry` | `above_vwap`, `below_vwap`, `unknown` | `market_above_vwap` on the signal bar |
| `trend_15m_at_entry`, `trend_60m_at_entry` | `up`, `down`, `flat`, `unknown` | A.7 values on the signal bar |
| `sim_kind` | `direct`, `index_as_future` | PLAN 4.4 |
| `vwap_kind` | `vwap`, `avg_price` | PLAN 4.2 |

`config/expiries.yaml` is filled by hand or, from T07, from the Kite instruments dump going forward. Historical dates may be incomplete; that is what `unknown` is for. Expiry weekdays have changed several times by exchange circular, so they are never derived from a weekday rule.

---

## Part C. Intraday strategies (intraday segment, square-off 15:20)

Shared rules:

- A strategy instance keeps per-symbol, per-session state and resets it in `on_day_start`.
- "At most one signal per symbol per session" counts signals **emitted by this instance**, whether or not risk approved them.
- **Opening range**: strategies with an `or_minutes` parameter use `OR = view.opening_range(or_minutes)` (A.3) and `or_end = session_open + or_minutes`. If `OR` is `None`, emit nothing.
- **Stop buffer**: strategies with a `stop_buffer_atr` parameter (default `0.0`) place a level-based stop at `level - stop_buffer_atr * atr14` for longs and `level + stop_buffer_atr * atr14` for shorts. If `stop_buffer_atr > 0` and `atr14` is missing, emit nothing. This exists to test whether stops placed exactly on obvious levels are being hunted (PLAN 9.5); changing it from the default is a spec change.
- **Risk bounds**: `risk_pct = abs(close - stop) / close * 100` on the signal bar must satisfy `min_risk_pct <= risk_pct <= max_risk_pct`. Outside the bounds, emit nothing.
- If any feature a condition needs is missing (`NaN` / `None`), that condition is **false**, unless the spec says the check is skipped.
- Every signal's `features` dict includes at least: `close`, `vwap`, `atr14`, `risk_pct`, `tod_rvol`, `or_rvol`, `gap_pct`, `market_above_vwap`, `trend_15m`, `trend_60m`, `daily_trend`, plus anything strategy-specific listed below.

### C.1 `orb_momentum` v1: opening range breakout with trend and volume filters

Idea: on active days the first move out of the opening range tends to continue. Evidence: US studies on QQQ and on high-relative-volume "stocks in play".

Scope: indices, and stocks that are in play.

Parameters (defaults): `or_minutes = 15`, `entry_end = 11:00`, `min_or_rvol = 1.5`, `min_risk_pct = 0.15`, `max_risk_pct = 1.0`, `target_r = 2.0`, `require_market_agree = true`, `stop_buffer_atr = 0.0`.

Long signal at bar T when all hold:

1. `T >= or_end` and `T < entry_end`.
2. `close > OR.high`, and this is the **first** bar today with open time `>= or_end` to close above `OR.high`.
3. This instance has emitted no signal for this symbol this session.
4. Opening direction is up: `OR.close > OR.open`.
5. `close > vwap`.
6. Stocks only: `in_play` is true and `day.or_rvol >= min_or_rvol`. Skipped for indices.
7. If `require_market_agree` and the symbol is not the market symbol: `market_above_vwap` is true. Skipped if `BarView.market` is `None`.
8. `stop = OR.low` with the stop buffer applied; risk bounds hold.

Then: `target = close + target_r * (close - stop)`, `time_exit = None`.

Short signal: mirror every inequality (`close < OR.low` and first close below it, opening direction down, `close < vwap`, market below VWAP, `stop = OR.high` with buffer, `target = close - target_r * (stop - close)`).

Extra features to log: `or_high`, `or_low`, `or_width_pct`, `opening_dir`.

### C.2 `failed_orb_fade` v1: trade the false breakout

Idea: when a breakout of the opening range fails quickly, trapped traders exit and price travels back through the range. This is the opening-range trap, traded from the other side.

Scope: all symbols in the universe. No in-play requirement.

Parameters: `or_minutes = 15`, `bo_end = 11:00`, `fail_window_minutes = 30`, `min_risk_pct = 0.15`, `max_risk_pct = 1.0`, `min_reward_risk = 1.0`, `stop_buffer_atr = 0.0`.

State per symbol per session, for each direction independently:

- **Upside breakout event**: the first bar B today with `B >= or_end`, `B < bo_end` and `close > OR.high`. Only the first such event per session counts.
- From B onward track `bo_extreme = max(high)` of bars B..current.

Short signal at bar T when all hold:

1. An upside breakout event exists at bar B, `T > B`, and `close_time(T) <= close_time(B) + fail_window_minutes`.
2. `close < OR.high` (closed back inside the range).
3. This instance has emitted no signal for this symbol this session.
4. `stop = bo_extreme` with the stop buffer applied; risk bounds hold.
5. `target = OR.low`, and `(close - target) / (stop - close) >= min_reward_risk`.

Long signal: mirror, using a downside breakout event (`close < OR.low`), `bo_extreme = min(low)`, `close > OR.low`, `stop = bo_extreme` with buffer, `target = OR.high`.

Extra features: `or_high`, `or_low`, `minutes_since_breakout`, `bo_extreme`, `reward_risk`.

### C.3 `overextension_fade` v1: fade stretched moves back to VWAP

Idea: sharp intraday extremes in Indian stocks have been reported to reverse within minutes.

Scope: all symbols.

Parameters: `window_start = 10:00`, `window_end = 14:30`, `z_entry = 3.0`, `z_lookback_bars = 3`, `min_risk_pct = 0.15`, `max_risk_pct = 1.0`, `min_reward_risk = 1.0`.

Definition: `z = (close - vwap) / atr14`, missing if `atr14` is missing or `<= 0`.

Short signal at bar T when all hold:

1. T in `[window_start, window_end)`.
2. `max(z over the last z_lookback_bars bars including T) >= z_entry`. All bars used must be in the same session.
3. Reversal trigger: `close < prev.low`.
4. `close > vwap`.
5. This instance has emitted no signal for this symbol this session.
6. `stop = day_high` (as of bar T); risk bounds hold.
7. `target = vwap` (value on bar T, fixed thereafter), and `(close - target) / (stop - close) >= min_reward_risk`.

Long signal: mirror (`min(z) <= -z_entry`, `close > prev.high`, `close < vwap`, `stop = day_low`, `target = vwap`).

Extra features: `z`, `z_extreme`, `reward_risk`.

### C.4 `intraday_contraction` v1: tightening range, then breakout (VCP idea on intraday bars)

Idea: a stock in play that trends above VWAP, pauses in progressively tighter ranges on fading volume, then breaks out on a volume surge.

Scope: stocks that are in play. Long only in v1.

Parameters: `window_start = 10:15`, `window_end = 14:30`, `block_bars = 4`, `n_blocks = 3`, `max_final_to_first_range = 0.5`, `max_base_rvol = 0.8`, `min_trigger_rvol = 1.5`, `min_risk_pct = 0.15`, `max_risk_pct = 1.0`, `target_r = 2.0`, `stop_buffer_atr = 0.0`.

At bar T with index `i` in the session's timeframe grid (0-based), require that the 12 bars `i-12 .. i-1` all exist. That is the **consolidation**; split it into blocks `b1 = i-12..i-9`, `b2 = i-8..i-5`, `b3 = i-4..i-1`. For each block, `range_k = max(high) - min(low)`.

Long signal at bar T when all hold:

1. T in `[window_start, window_end)`; `in_play` is true.
2. `range_3 < range_2 < range_1`.
3. `range_3 <= max_final_to_first_range * range_1`.
4. Mean `tod_rvol` of block `b3` `< max_base_rvol` (any missing value makes this false).
5. Bar `i-1` has `close > vwap`.
6. `pivot = max(high)` of the consolidation; `close > pivot`.
7. `tod_rvol` of bar T `>= min_trigger_rvol`.
8. This instance has emitted no signal for this symbol this session.
9. `stop = min(low)` of block `b3` with the stop buffer applied; risk bounds hold.

Then: `target = close + target_r * (close - stop)`.

Extra features: `range_1`, `range_2`, `range_3`, `base_rvol`, `trigger_rvol`, `pivot`.

Note: on `15minute` the consolidation spans three hours, so signals can only appear from about 12:15.

### C.5 `first_half_hour_momentum` v1: opening move predicts the close

Idea: the market's return in the first half hour has been shown to predict the direction of the last half hour in the US and several other markets.

Scope: indices only.

Parameters: `measure_time = 09:45`, `signal_time = 15:00`, `min_move_pct = 0.2`, `stop_pct = 0.3`. Class attribute `allow_late_entry = True`.

1. At the first bar with `close_time >= measure_time`: `r_open = (close / prev_close - 1) * 100`, using `DayContext.prev_close`. If `prev_close` is `None`, no trade today.
2. At the first bar with `close_time >= signal_time`: if `abs(r_open) >= min_move_pct`, emit a signal in the direction of `r_open`.
3. Long: `stop = close * (1 - stop_pct / 100)`. Short: `stop = close * (1 + stop_pct / 100)`.
4. `target = None`, `time_exit = None`. The trade exits at square-off (15:20).

Risk bounds are not applied (the stop is a fixed percentage). The rule depends on clock times, not on bar size, so one instance (`5minute`) is enough.

Note: this holds for about 20 minutes and pays a full futures round trip (about 14 index points per lot at current charges). It is included because it is the best-documented effect, and expected to struggle after costs. That is a useful result either way.

Extra features: `r_open`.

### C.6 `sweep_reversal` v1: trade the stop run at yesterday's high or low

Idea: stops cluster just beyond the previous day's high and low. Price often pokes through, triggers them, finds no follow-through and reverses. Instead of being the trader whose stop is hit, enter after the poke fails.

Scope: all symbols.

Parameters: `window_start = 09:30`, `window_end = 14:30`, `reclaim_minutes = 15`, `max_sweep_pct = 0.5`, `min_risk_pct = 0.15`, `max_risk_pct = 1.0`, `target_r = 2.0`, `stop_buffer_atr = 0.0`.

Levels: `PDH = day.prev_day_high`, `PDL = day.prev_day_low`. If either is `None`, emit nothing for that side.

State per symbol per session, for each side independently:

- **Upside sweep event**: the first bar S today with `high > PDH`. It counts only if S is in `[window_start, window_end)` and today's first base bar opened at or below `PDH`. If the first bar to exceed `PDH` falls outside the window, there is no upside event today.
- From S onward track `sweep_extreme = max(high)` of bars S..current.

Short signal at bar T when all hold:

1. An upside sweep event exists at bar S, `T >= S` (the sweep bar itself qualifies), and `close_time(T) <= close_time(S) + reclaim_minutes`.
2. `close < PDH` (price is back below the level).
3. `sweep_pct = (sweep_extreme - PDH) / PDH * 100 <= max_sweep_pct` (a poke, not a real breakout).
4. This instance has emitted no signal for this symbol this session.
5. `stop = sweep_extreme` with the stop buffer applied; risk bounds hold.

Then: `target = close - target_r * (stop - close)`.

Long signal: mirror with `PDL` (`low < PDL`, first base bar opened at or above `PDL`, `sweep_extreme = min(low)`, `close > PDL`, `sweep_pct = (PDL - sweep_extreme) / PDL * 100`, `stop = sweep_extreme` with buffer, `target = close + target_r * (close - stop)`).

Extra features: `level`, `level_kind` (`pdh` or `pdl`), `sweep_extreme`, `sweep_pct`, `minutes_since_sweep`.

If both sides qualify on the same bar, the short (upside sweep) is taken; the one-signal-per-session rule then blocks the other.

---

## Part D. Swing strategy (phase 7, daily bars). Draft; review with the owner before implementing.

### D.1 `swing_vcp` v1: volatility contraction pattern

Scope: stocks. Segment `EQ_DELIVERY`. Long only. Runs once per session after the close; entries at the next session's open.

Daily features (all use data up to and including day t): `sma50`, `sma150`, `sma200` of close; `high_252`, `low_252` (max high / min low of the last 252 sessions); `vol_sma50`.

Parameters: `base_lookback = 65`, `zigzag_pct = 3.0`, `min_contractions = 2`, `max_contractions = 4`, `max_first_depth_pct = 35`, `max_depth_ratio = 0.7`, `max_last_depth_pct = 10`, `dryup_days = 10`, `min_breakout_vol_ratio = 1.5`, `stop_lookback = 10`, `max_risk_pct = 8.0`, `max_hold_days = 40`.

**Trend template** on day t:

1. `close > sma50 > sma150 > sma200`
2. `sma200[t] > sma200[t-20]`
3. `close >= 1.25 * low_252` and `close >= 0.75 * high_252`

**Contractions** in the window of `base_lookback` sessions ending at t-1, using a zigzag with reversal threshold `thr = zigzag_pct / 100`:

```
i0 = index of the maximum high in the window (leftmost if tied)
peak = high[i0]; mode = "down"; run_low = +inf; run_high = peak
swings = []                                   # (peak, trough) pairs
for j in i0+1 .. last index of window:
    if mode == "down":
        run_low = min(run_low, low[j])
        if (peak - run_low) / peak >= thr and high[j] >= run_low * (1 + thr):
            swings.append((peak, run_low)); mode = "up"; run_high = high[j]
    else:
        run_high = max(run_high, high[j])
        if low[j] <= run_high * (1 - thr):
            peak = run_high; mode = "down"; run_low = low[j]
if mode == "down" and run_low != +inf and (peak - run_low) / peak >= thr:
    swings.append((peak, run_low))            # unfinished final pullback counts
pivot = run_high if mode == "up" else peak
depth_k = (peak_k - trough_k) / peak_k * 100
```

Conditions:

4. `min_contractions <= len(swings) <= max_contractions`
5. `depth_1 <= max_first_depth_pct`
6. For every consecutive pair: `depth_{k+1} <= max_depth_ratio * depth_k`
7. `depth_last <= max_last_depth_pct`
8. Volume dry-up: mean volume of the last `dryup_days` sessions of the window `<` `vol_sma50[t-1]`

**Trigger** on day t: `close[t] > pivot` and `volume[t] >= min_breakout_vol_ratio * vol_sma50[t-1]`.

**Entry**: next session's open. **Stop**: lowest low of the `stop_lookback` sessions ending at t. Skip if `(close[t] - stop) / close[t] * 100 > max_risk_pct`.

**Exits**, checked daily:

- Stop: gap below the stop exits at the open, otherwise at the stop price. Reason `STOP`.
- Close below `sma50`: exit at the next session's open. Reason `RULE`.
- Held `max_hold_days` sessions: exit at the next session's open. Reason `TIME`.

No profit target in v1.

---

## Part E. Planned, not yet specified

- **Expiry-day setups and options** (T20): needs option data, a fill model for wide spreads, and time decay. Write the design before any code.
- **Higher-timeframe filters**: for example, take `orb_momentum` longs only when `trend_60m` is `up`. Decide from the scoreboard after enough trades are logged with those tags.
- **Retest entries**: instead of entering on the breakout bar, wait for price to return to the broken level and hold. A common answer to traps; needs its own precise spec.
- **Other trap levels**: round numbers, the day's own high and low, heavy open-interest strikes.
- **News-driven in-play flag** (phase 6).
- **Short side for `intraday_contraction`**.

New ideas go to `docs/hypotheses/` as a short spec in the same style as Part C, and enter the build only after the owner approves them.
