#!/usr/bin/env bash
# Weekly proof that backups restore: loads the latest Postgres dump into a scratch database next to
# the live one, compares row counts of the main tables, then drops it. Alerts on any failure.
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'deploy/notify.sh "restore test FAILED at line ${LINENO}; backups may not be usable"' ERR
: "${TRADEMIND_BACKUP_BUCKET:?set TRADEMIND_BACKUP_BUCKET}"
latest=$(aws s3 ls "s3://${TRADEMIND_BACKUP_BUCKET}/postgres/" | awk '{print $4}' | sort | tail -n 1)
[ -n "$latest" ] || { echo "no backups found" >&2; false; }
psql() { docker compose exec -T db psql -U trademind -v ON_ERROR_STOP=1 "$@"; }
psql -d trademind -c "DROP DATABASE IF EXISTS trademind_restore_test" >/dev/null
psql -d trademind -c "CREATE DATABASE trademind_restore_test" >/dev/null
aws s3 cp "s3://${TRADEMIND_BACKUP_BUCKET}/postgres/${latest}" - | gunzip | psql -d trademind_restore_test -q >/dev/null
for table in runs trades signals; do
  restored=$(psql -d trademind_restore_test -tAc "SELECT count(*) FROM ${table}")
  live=$(psql -d trademind -tAc "SELECT count(*) FROM ${table}")
  echo "${table}: restored ${restored}, live ${live}"
  # The dump is from last night, so the live table may only have grown since.
  [ "$restored" -gt 0 ] && [ "$restored" -le "$live" ] || { echo "${table} does not match" >&2; false; }
done
psql -d trademind -c "DROP DATABASE trademind_restore_test" >/dev/null
echo "restore test of ${latest} passed"
