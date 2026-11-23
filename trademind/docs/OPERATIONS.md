# Operations guide

How to run TRADEMIND every trading day: on your laptop, or unattended on one AWS instance.

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
trademind data download --start 2025-05-01 --end 2025-11-14
trademind data instruments            # checks lot sizes; add --write-expiries to record expiries
```

Each `paper run` appends that day's bars, so history grows by itself afterwards.

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
docker compose run --rm api trademind data download --start 2025-05-01 --end $(date -d yesterday +%F)
sudo cp deploy/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trademind-daily.timer trademind-backup.timer
systemctl list-timers | grep trademind
```

Use a fine-grained GitHub token limited to this repository with read-only contents access. To update later: `git pull && docker compose up -d --build`.

### What happens each weekday
| Time (IST) | Event |
|---|---|
| 08:40 | Telegram: "Kite login needed" with the login link |
| You | Log in on your phone, copy the address you land on, send it to the bot |
| 08:40-09:15 | Login confirmed on Telegram; the runner loads history and waits for the open |
| 09:15-15:30 | Paper trades from live ticks; Telegram message on every paper entry and exit |
| 15:30 | Journal written, today's bars stored, daily summary on Telegram |
| 20:00 | Postgres dump and bar store backed up to S3 |

If no login arrives within 30 minutes, the bot says so and that day is skipped. Holidays simply produce a day with no trades.

### Looking at results
```bash
aws ssm start-session ... (terraform output api_tunnel)    # then open http://127.0.0.1:8000/dashboard
curl -H "Authorization: Bearer $TRADEMIND_API_TOKEN" http://127.0.0.1:8000/runs
docker compose run --rm api trademind runs
docker compose run --rm api trademind report --run-id <id> --by time_bucket
```

### Backups and restore
`deploy/backup.sh` runs nightly. To restore a day: `./deploy/restore.sh 2026-11-17`. Test a restore once after setup.

### Costs to expect (owner's ceiling: Rs 10,000 a month, all in)
| Item | Rs / month, approx. |
|---|---|
| AWS server: t4g.medium (~$0.0224/hr in ap-south-1), 30 GB gp3, public IP, backups | ~2,400 incl. GST |
| Kite Connect (real-time and historical data) | 500 + GST |
| Claude Pro, for the ops agent (docs/AGENT.md) | 2,399 monthly, or 2,000 billed yearly |
| Bedrock research notes, capped at `research.monthly_budget_usd` ($15) | up to ~1,600 |
| Bedrock agent fallback, capped at `AGENT_BEDROCK_MONTHLY_USD` ($20) | up to ~2,100 |
| **Total** | **~9,100** |

The AWS budget alert emails you at 80% of `monthly_budget_usd` (default $60: server plus both Bedrock caps). Claude Max (from Rs 11,999) does not fit the ceiling.

## 4. AI research notes (optional)
1. In the Bedrock console (ap-south-1), enable access to an Anthropic Haiku-class and a Sonnet-class model and copy their model or inference-profile ids.
2. In `config/settings.yaml` under `research:`, set `enabled: true`, `routine_model`, `deep_model`, and a `prices` entry for each id (USD per million input and output tokens, from the Bedrock pricing page).
3. The instance role already allows `bedrock:InvokeModel`. On a laptop, use your AWS credentials.

After each trading day `trademind research postmortem` writes `data/reports/<day>-postmortem.md` and sends a short Telegram note; on Fridays `trademind research weekly` writes at most two proposals to `data/research/`. Nothing is applied automatically. Spend stops at `monthly_budget_usd`.

### Ops agent (optional)
Claude Code can work on the server for you on Bedrock: run tests and backtests, do cards, check status, deploy merged `main`. Setup and guardrails: [`AGENT.md`](AGENT.md).

## 5. Troubleshooting
| Symptom | Fix |
|---|---|
| `no Kite session for today` | Run `trademind login` (sessions expire daily) |
| `no stored history for NIFTY 50` | Run `trademind data download` for a few months |
| No Telegram messages | Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`; send the bot a message first |
| Daily timer did nothing | `journalctl -u trademind-daily -n 200` |
| Lot sizes look wrong | `trademind data instruments`; the runner uses Kite's values when it starts |

## 6. Before any real money (not built, by design)
All of these are required, and none is automated:
1. A strategy version passes `trademind validate`.
2. At least 60 live paper trades for that version, with expectancy inside the research confidence interval.
3. Charges in `config/costs.yaml` re-checked.
4. The Elastic IP whitelisted in Kite (SEBI static-IP rule for API orders), staying under 10 orders per second.
5. An order-execution module written, reviewed and tested separately. Today the code base cannot place orders at all.
