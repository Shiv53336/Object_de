#!/usr/bin/env bash
# Restore: ./deploy/restore.sh 2026-11-17   (that day's Postgres dump, the bar stores, the ledger)
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TRADEMIND_BACKUP_BUCKET:?set TRADEMIND_BACKUP_BUCKET}"
day="${1:?usage: restore.sh YYYY-MM-DD}"
aws s3 cp "s3://${TRADEMIND_BACKUP_BUCKET}/postgres/trademind-${day}.sql.gz" - | gunzip \
  | docker compose exec -T db psql -U trademind -d trademind
aws s3 sync "s3://${TRADEMIND_BACKUP_BUCKET}/bars" data/bars --only-show-errors
aws s3 sync "s3://${TRADEMIND_BACKUP_BUCKET}/bars_live" data/bars_live --only-show-errors
aws s3 sync "s3://${TRADEMIND_BACKUP_BUCKET}/ledger" ledger --only-show-errors
echo "restored ${day}"
