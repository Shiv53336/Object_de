#!/usr/bin/env bash
# Nightly backup: Postgres dump and the Parquet bar store to S3. Needs TRADEMIND_BACKUP_BUCKET.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TRADEMIND_BACKUP_BUCKET:?set TRADEMIND_BACKUP_BUCKET (terraform output backup_bucket)}"
stamp=$(date +%F)
docker compose exec -T db pg_dump -U trademind -d trademind | gzip > "/tmp/trademind-${stamp}.sql.gz"
aws s3 cp "/tmp/trademind-${stamp}.sql.gz" "s3://${TRADEMIND_BACKUP_BUCKET}/postgres/trademind-${stamp}.sql.gz"
rm -f "/tmp/trademind-${stamp}.sql.gz"
aws s3 sync data/bars "s3://${TRADEMIND_BACKUP_BUCKET}/bars" --only-show-errors
echo "backup ${stamp} done"
