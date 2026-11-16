#!/usr/bin/env bash
# Trading-day routine on the server: Telegram login, then live paper trading until 15:30.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d db
docker compose run --rm api trademind login --telegram --timeout 1800
docker compose run --rm api trademind paper run
# Advisory AI notes; skipped quietly when research is disabled or the budget is spent.
docker compose run --rm api trademind research postmortem || true
if [ "$(date +%u)" = "5" ]; then
  docker compose run --rm api trademind research weekly || true
fi
