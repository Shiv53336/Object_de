#!/usr/bin/env bash
# Send one Telegram message using TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID from the environment or .env.
# Never fails the caller: a missing token or a network error only prints a warning.
#   deploy/notify.sh "backup failed"
text="TRADEMIND: ${1:?message}"
cd "$(dirname "$0")/.." || exit 0
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] && [ -f .env ]; then
  TELEGRAM_BOT_TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2- || true)
  TELEGRAM_CHAT_ID=$(grep -E '^TELEGRAM_CHAT_ID=' .env | cut -d= -f2- || true)
fi
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "notify: Telegram not configured: $text" >&2
  exit 0
fi
curl -fsS -m 15 -o /dev/null "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=${text}" \
  || echo "notify: could not reach Telegram: $text" >&2
exit 0
