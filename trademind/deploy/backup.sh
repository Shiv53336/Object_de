#!/usr/bin/env bash
# Nightly backup: Postgres dump, the research ledger and both bar stores (exchange candles, live) to S3.
# Needs TRADEMIND_BACKUP_BUCKET. Any failure sends a Telegram alert (deploy/notify.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'deploy/notify.sh "backup FAILED at line ${LINENO}; check: journalctl -u trademind-backup"' ERR
: "${TRADEMIND_BACKUP_BUCKET:?set TRADEMIND_BACKUP_BUCKET (terraform output backup_bucket)}"
stamp=$(date +%F)
dump="/tmp/trademind-${stamp}.sql.gz"
docker compose exec -T db pg_dump -U trademind -d trademind | gzip > "$dump"
[ "$(stat -c %s "$dump")" -gt 1000 ] || { echo "dump is suspiciously small" >&2; false; }
aws s3 cp "$dump" "s3://${TRADEMIND_BACKUP_BUCKET}/postgres/trademind-${stamp}.sql.gz" --only-show-errors
rm -f "$dump"
aws s3 sync data/bars "s3://${TRADEMIND_BACKUP_BUCKET}/bars" --only-show-errors
[ ! -d data/bars_live ] || aws s3 sync data/bars_live "s3://${TRADEMIND_BACKUP_BUCKET}/bars_live" --only-show-errors
aws s3 sync ledger "s3://${TRADEMIND_BACKUP_BUCKET}/ledger" --only-show-errors
echo "backup ${stamp} done"
