#!/usr/bin/env bash
# Trading-day routine on the server: Telegram login, last week's candles, preflight, live paper
# trading until 15:30, then the paper-vs-replay check.
set -euo pipefail
cd "$(dirname "$0")/.."
tm() { docker compose run --rm api trademind "$@"; }
docker compose up -d db
tm login --telegram --timeout 1800
# Yesterday's official candles become history; live tick bars never do.
tm data download --start "$(date -d '7 days ago' +%F)" --end "$(date -d yesterday +%F)" \
  || echo "warning: download failed; preflight decides whether history is fresh enough"
tm preflight --for paper
tm paper run
tm paper check || echo "PAPER CHECK FAILED: keep data/checks/$(date +%F).md for review"
# Advisory AI notes; skipped quietly when research is disabled or the budget is spent.
tm research postmortem || true
# The weekly AI review is paused until a strategy passes the gate (2026-11-23 review, docs/CHARTER.md).
