# Operations guide

How to run TRADEMIND every trading day: on your laptop, or unattended on one AWS instance. Test on the laptop first ([`TESTING.md`](TESTING.md)); the server starts only after that passes ([`CHARTER.md`](CHARTER.md)).

## 1. One-time setup

### Zerodha Kite Connect
1. Create an app at developers.kite.trade on the paid Connect plan (Rs 500/month, includes historical and live data).
2. Set the app's redirect URL to `https://127.0.0.1/`. The page will not load after login, which is fine: the address bar then contains `request_token=...`, and that is all TRADEMIND needs.
3. Put `KITE_API_KEY` and `KITE_API_SECRET` in `trademind/.env`. Never paste them into chat or commit them.

### Telegram (alerts and the daily login on your phone)
1. In Telegram, message @BotFather, send `/newbot`, and copy the bot token into `TELEGRAM_BOT_TOKEN`.
2. Send any message to your new bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `message.chat.id` into `TELEGRAM_CHAT_ID`.
3. The bot only accepts login replies from that chat id.

### History
The live runner and the features need history. Download once (Kite serves minute data in 60-day chunks; the command handles it):

```bash
trademind data download --start 2024-11-01 --end <yesterday>
trademind data validate --symbol all --start 2024-11-01 --end <yesterday>
trademind data instruments            # checks lot sizes; add --write-expiries to record expiries
```

The start date covers the warmup before the research period (2025-05-01). Official candles go to `data/bars`, the only store research reads. Live tick-built bars go to `data/bars_live` and never become history. The daily routine downloads the last week's official candles each morning, so history grows by itself. `data validate` flags overnight jumps over 20%; record real splits and bonuses in `config/corporate_actions.yaml` (`TESTING.md` step 2).

## 2. Laptop

```bash
cd trademind && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
set -a; source .env; set +a
trademind login          # or: trademind login --telegram
trademind paper run      # keep the laptop awake until 15:30
```

## 3. AWS (unattended)

Region ap-south-1 (Mumbai), one Graviton instance, no inbound ports, access only through SSM.

```bash
cd trademind/infra/terraform
cp terraform.tfvars.example terraform.tfvars   # set alert_email
terraform init && terraform apply
terraform output                               # instance id, static IP, backup bucket, SSM commands
```

Then on the instance (`terraform output connect` gives the command):

```bash
sudo su - ec2-user
cd /opt/trademind
git clone https://<github-user>:<fine-grained-read-only-token>@github.com/Shiv53336/Object_de.git .
cd trademind
cp .env.example .env && chmod 600 .env && vi .env      # Postgres password, API token, Kite, Telegram
echo "TRADEMIND_BACKUP_BUCKET=$(aws s3 ls | awk '/trademind-backup-/{print $3}')" >> .env
mkdir -p data
docker compose up -d --build
docker compose run --rm api trademind data download --start 2024-11-01 --end $(date -d yesterday +%F)
sudo cp deploy/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trademind-daily.timer trademind-backup.timer trademind-restore-test.timer
systemctl list-timers | grep trademind
```

Use a fine-grained GitHub token limited to this repository with read-only contents access. To update later: `git pull && docker compose up -d --build`.

### What happens each weekday
| Time (IST) | Event |
|---|---|
| 08:40 | Telegram: "Kite login needed" with the login link |
| You | Log in on your phone, copy the address you land on, send it to the bot |
| 08:40-09:15 | Login confirmed on Telegram; last week's official candles downloaded; preflight; the runner loads history and waits for the open |
| 09:15-15:30 | Paper trades from live ticks; Telegram message on every paper entry and exit, and if market data stops |
| 15:30 | Journal written, today's live bars stored, daily summary on Telegram |
| ~15:31 | `paper check` writes `data/checks/<day>.md` (replay parity and execution drift) |
| 20:00 | Postgres dump, both bar stores (official and live) and the research ledger backed up to S3; Telegram alert if it fails |
| Sunday 10:00 | Restore test: the latest dump is restored into a scratch database and its row counts checked; Telegram alert if it fails |

If no login arrives within 30 minutes, the bot says so and that day is skipped. Holidays simply produce a day with no trades.

A run ends `done`, `stopped`, `crashed` (with a Telegram alert) or `superseded` (restarted the same day). Only `done` days count as paper days. To restart a crashed day: `docker compose run --rm api trademind paper run`.

**Holdout checks (`trademind validate`) run on the laptop only.** Each look is recorded in `ledger/`, which must be committed and pushed; the server has a read-only token and cannot push.

### Looking at results
```bash
aws ssm start-session ... (terraform output api_tunnel)    # then open http://127.0.0.1:8000/dashboard
curl -H "Authorization: Bearer $TRADEMIND_API_TOKEN" http://127.0.0.1:8000/runs
docker compose run --rm api trademind runs
docker compose run --rm api trademind report --run-id <id> --by time_bucket
```

### Backups and restore
- **Nightly:** `deploy/backup.sh` runs. It checks the dump is not empty and copies the research ledger as well.
- **Failures:** any failure sends a Telegram alert (`deploy/notify.sh`).
- **Weekly:** `deploy/restore-test.sh` proves the latest backup restores.
- **To restore a day:** `./deploy/restore.sh 2026-11-17`. This brings back the database and the ledger.

### Costs to expect (owner's ceiling: Rs 10,000 a month, all in)
| Item | Rs / month, approx. |
|---|---|
| AWS server: t4g.medium (~$0.0224/hr in ap-south-1), 30 GB gp3, public IP, backups | ~2,400 incl. GST |
| Kite Connect (real-time and historical data) | 500 + GST |
| Claude Pro, for the ops agent (docs/AGENT.md) | 2,399 monthly, or 2,000 billed yearly |
| Bedrock research notes, capped at `research.monthly_budget_usd` ($15) | up to ~1,600 |
| Bedrock agent fallback | 0 (off by default; `AGENT_BEDROCK_MONTHLY_USD`) |
| **Total** | **~7,000** |

The AWS budget alert emails you at 80% of `monthly_budget_usd` (default $45: server plus research Bedrock, with room to spare). If you turn the agent's Bedrock fallback on, its cap is also enforced by an AWS Budgets action that cuts off Bedrock (`AGENT.md`). Claude Max (from Rs 11,999) does not fit the ceiling for more than an occasional month.

## 4. AI research notes (optional)
1. In the Bedrock console (ap-south-1), enable access to an Anthropic Haiku-class and a Sonnet-class model and copy their model or inference-profile ids.
2. In `config/settings.yaml` under `research:`, set `enabled: true`, `routine_model`, `deep_model`, and a `prices` entry for each id (USD per million input and output tokens, from the Bedrock pricing page).
3. The instance role already allows `bedrock:InvokeModel`. On a laptop, use your AWS credentials.

After each trading day `trademind research postmortem` writes `data/reports/<day>-postmortem.md` and sends a short Telegram note. The weekly review (`trademind research weekly`, at most two proposals to `data/research/`) is paused in the daily routine until a strategy passes the gate (`CHARTER.md`). Nothing is applied automatically. Spend stops at `monthly_budget_usd`.

### Ops agent (optional)
Claude Code can work on the server for you on your Claude plan: run tests and backtests, do cards, check status, deploy merged `main`. The repo must be private before the runner is registered. Setup and guardrails: [`AGENT.md`](AGENT.md).

## 5. Troubleshooting
| Symptom | Fix |
|---|---|
| `no Kite session for today` | Run `trademind login` (sessions expire daily) |
| `no stored history for NIFTY 50` | Run `trademind data download` for a few months |
| No Telegram messages | Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`; send the bot a message first |
| Daily timer did nothing | `journalctl -u trademind-daily -n 200` |
| Telegram "backup FAILED" or "restore test FAILED" | `journalctl -u trademind-backup -n 100` (or `trademind-restore-test`); check disk space and the S3 bucket |
| A run shows `crashed` | Read the alert and `journalctl -u trademind-daily`; restart `paper run` the same day |
| Lot sizes look wrong | `trademind data instruments`; the runner uses Kite's values when it starts |

## 6. Before any real money (not built, by design)
All of these are required, and none is automated:
1. The charter's decision on 2027-03-31 is "continue" (`CHARTER.md`).
2. A strategy version passes `trademind validate`.
3. At least 60 live paper trades for that version, with expectancy inside the research confidence interval.
4. Charges in `config/costs.yaml` re-checked.
5. The Elastic IP whitelisted in Kite (SEBI static-IP rule for API orders), staying under 10 orders per second.
6. An order-execution module written, reviewed and tested separately. Today the code base cannot place orders at all.
