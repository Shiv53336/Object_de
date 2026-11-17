#!/usr/bin/env bash
# Read-only health report of the production checkout. The ops agent runs it through sudo as ec2-user
# (deploy/agent/sudoers). It prints no secrets: never add .env, tokens or `docker compose config` here.
set -uo pipefail
cd /opt/trademind/trademind || exit 1

echo "== deployed commit"
git log -1 --format='%h %ad %s' --date=format:'%Y-%m-%d %H:%M'
echo
echo "== containers"
docker compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
echo
echo "== timers"
systemctl list-timers 'trademind-*' --no-pager
echo
echo "== last daily run (tail)"
journalctl -u trademind-daily.service -n 60 --no-pager -o cat 2>/dev/null || echo "(journal not readable)"
echo
echo "== last backup"
journalctl -u trademind-backup.service -n 5 --no-pager -o short-iso 2>/dev/null || echo "(journal not readable)"
echo
echo "== recent runs in the journal database"
timeout 120 docker compose run --rm -T api trademind runs --limit 5 2>&1 | tail -n 12
echo
echo "== disk and memory"
df -h / | tail -n 1
free -m | sed -n 2p
