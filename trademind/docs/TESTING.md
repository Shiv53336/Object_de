# Local testing on Windows with VS Code

This phase proves TRADEMIND is correct on **real data** before it runs unattended on a server. Every step has a pass bar. Don't start the next step until the current one passes. When something fails, keep the evidence (logs, `data/checks/*.md`) and fix the cause, not the symptom.

Paper only, always: nothing in this repo can place an order.

| Step | What | Time | Pass bar |
|---|---|---|---|
| 1 | Install | 30 min | All tests green on your laptop |
| 2 | Real data | 1 hour | Every symbol downloaded and validated; lot sizes match Kite |
| 3 | Backtest on real data | 1 evening | Runs end to end; identical twice; costs match Zerodha's calculator |
| 4 | Holdout check | 1 evening | Read once, honestly, no tuning afterwards |
| 5 | Live paper on the laptop | 10 market days | No crashes; preflight READY; paper check PASS every day |

## 1. Install (once)

**Windows settings first:**
- Settings > Time & language: time zone **(UTC+05:30) Chennai, Kolkata, Mumbai, New Delhi**, with "Set time automatically" on.
- Control Panel > Power Options > Choose what closing the lid does: **Plugged in: Do nothing**.
- Change plan settings > Advanced: **Allow wake timers: Enable** (lets the 08:45 task wake the laptop).

**Install the tools.** In PowerShell:
```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
winget install -e --id Microsoft.VisualStudioCode
```
Close and reopen PowerShell, then:
```powershell
cd $HOME
git clone https://github.com/Shiv53336/Object_de.git      # sign in to GitHub when the browser opens
cd Object_de\trademind
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -e ".[dev]"
pytest -q
copy .env.example .env
code .
```

**In VS Code:**
- Accept the "recommended extensions" prompt. It installs Claude Code, Python, Ruff and YAML.
- Sign in to Claude Code with your Claude account.
- Every command below is also a **Terminal > Run Task > TM: …** entry.

**Pass:** `pytest -q` ends with all tests passed. A few tests are skipped because they are Linux-only.

## 2. Real data

1. Create a Kite Connect app at developers.kite.trade. Use the ₹500/month plan, which includes historical and live data. Redirect URL: `http://127.0.0.1`.
2. Put `KITE_API_KEY` and `KITE_API_SECRET` in `.env`, plus the Telegram values if you want alerts.
   - Type them into the file yourself.
   - Never paste them into a chat, Claude Code included.
   - Claude Code is blocked from reading `.env`.
3. Run:
```powershell
trademind login                     # opens Kite in your browser; paste back the address you land on
trademind data instruments          # lot sizes from Kite vs config/settings.yaml
trademind data download --start 2024-11-01 --end <yesterday>
trademind data validate --symbol all --start 2024-11-01 --end <yesterday>
```

About the download range:
- It starts at 2024-11-01, which covers the 160-day warmup before the research period (from 2025-05-01).
- It runs up to yesterday, so the holdout period is covered too.


**Pass:**
- Every symbol downloaded, and `data validate` says OK, or only `info:` lines, or each problem is explained (for example, a trading holiday).
- Every lot size that `data instruments` marks `<- differs from config` is fixed in `config/settings.yaml`. This applies especially to the index lot sizes, which are placeholders. Lot sizes are instrument facts, not strategy parameters, so changing them is fine.

## 3. Backtest on real data (research period only)

```powershell
trademind backtest --source parquet --start 2025-05-01 --end 2026-04-30 --by time_bucket
trademind backtest --source parquet --start 2025-05-01 --end 2026-04-30 --by market_regime
```

**Pass:**
- **Runs:** both finish with a scoreboard.
- **Identical twice:** running the first command again gives the same scoreboard, byte for byte.
- **Costs match:** pick three trades of different kinds (a stock, an index future, a short). Ask Claude Code: *"show these trades from the last run with their cost breakdown"*. Compare each with Zerodha's brokerage calculator; they should agree within ₹1.

**Don't tune.** If a strategy looks bad, write down what you see; don't change a parameter. Changes go through a spec change with a new strategy version (`CLAUDE.md`).

## 4. Holdout check (once)

The holdout period, from 2026-05-01 to yesterday, is the only data no decision has looked at. Each strategy version gets at most two looks.

Run it only for instances whose research scoreboard is worth checking: at least 100 trades and positive expectancy after costs.
```powershell
trademind validate --instance orb_momentum@5minute --source parquet --start 2026-05-01 --end <yesterday>
```
**Pass:** you read the report once and record the verdict in `docs/DECISIONS.md`, with no tuning afterwards.

## 5. Live paper on the laptop (10 market days)

**Once:** register the morning task:
```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\register-task.ps1
```

**Every market day, the task runs `deploy\windows\daily.ps1` at 08:45:**
1. **Kite login.** With Telegram set up, the login link comes to your phone; reply with the redirect URL. Otherwise, the task window asks you to paste the `request_token`. **Be there before 09:10.**
2. **`trademind preflight`.** Any FAIL stops the day, with the reason shown.
3. **`trademind paper run`** from 09:15 to 15:30. Windows sleep is blocked while it runs. Keep the laptop plugged in with the lid open.
4. **`trademind paper check`** at about 15:31. It writes `data\checks\YYYY-MM-DD.md`.

The whole day is logged in `data\logs\YYYY-MM-DD.log`.

**What the paper check compares:**

| Section | Compares | Expect |
|---|---|---|
| 1. Bars | Your live tick-built minute bars vs Kite's official candles | A few missing minutes or sub-percent volume gaps at most |
| 2. Replay on live bars | The live run vs a backtest of the same day on the same bars | **Exact match (PASS).** A FAIL is a bug: stop and investigate |
| 3. Replay on Kite candles | The live run vs a backtest on official candles | Small differences; big P&L swings mean a strategy is fragile |

**Daily log (copy into your notes):**

| Day | Preflight | Run to 15:30 | Check §2 | Bars | Notes |
|---|---|---|---|---|---|
| 1 | | | | | |

**Pass:** 10 market days in a row with READY, a completed run and PASS. Then move to the server (`OPERATIONS.md`).

## When something fails

| Symptom | Likely cause | Fix |
|---|---|---|
| Preflight `FAIL kite login` | No session for today | `trademind login` |
| Preflight `FAIL history` | No bars for the index | Step 2 download |
| Preflight `WARN freshness` | Yesterday's data missing (or a holiday) | `trademind data download --start <day> --end <day>` |
| Preflight `WARN/FAIL clock` | Windows clock drifted | Settings > Time > **Sync now** |
| Run stopped mid-day | Sleep, network drop, or crash | Read the day's log; restart `trademind paper run` (it backfills the missed minutes) |
| Check §1 `CHECK` | Missed ticks or a network gap | Compare with the log's timestamps |
| Check §2 `FAIL` | Engine, timing or data-loading bug | Keep `data\checks\DAY.md` and the log; ask Claude Code to investigate (prompt below) |

## Using Claude Code in VS Code

Claude Code follows `CLAUDE.md`. Its permissions (`.claude/settings.json`) do two things:
- **Lets it run on its own:** tests, lint, backtests, data download and validation, preflight, the paper check and git commits.
- **Blocks:** reading `.env`, pushing, the holdout command, `login` and `paper run`. Those are yours.

Prompts that work well:
- *"Run preflight and explain each WARN."*
- *"Validate every symbol from 2024-11-01 to yesterday and summarise the problems."*
- *"Run the research backtest twice and confirm the scoreboards are identical."*
- *"Read data/checks/2026-11-20.md and the log for that day. Find why section 2 failed. Don't change strategy parameters; propose a fix with a test."*

If Claude Code says `trademind` is not found, tell it to use `.venv\Scripts\trademind.exe`.
