#!/usr/bin/env bash
# Restore: ./deploy/restore.sh 2026-11-17   (restores that day's Postgres dump and the bar store)
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TRADEMIND_BACKUP_BUCKET:?set TRADEMIND_BACKUP_BUCKET}"
day="${1:?usage: restore.sh YYYY-MM-DD}"
aws s3 cp "s3://${TRADEMIND_BACKUP_BUCKET}/postgres/trademind-${day}.sql.gz" - | gunzip \
  | docker compose exec -T db psql -U trademind -d trademind
aws s3 sync "s3://${TRADEMIND_BACKUP_BUCKET}/bars" data/bars --only-show-errors
echo "restored ${day}"
