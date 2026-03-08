#!/usr/bin/env bash
# set-webhook.sh — Manually register the Telegram webhook
# Run this if docker-compose's webhook-setup service didn't fire,
# or if you changed the ngrok URL.
#
# Usage:
#   bash scripts/set-webhook.sh
#   NGROK_URL=https://your-new-url.ngrok-free.dev bash scripts/set-webhook.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env
if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN not set in .env}"
: "${NGROK_URL:?NGROK_URL not set in .env}"

WEBHOOK_URL="${NGROK_URL}/webhook/telegram-bot-webhook"

echo "🔗 Setting Telegram webhook..."
echo "   URL: ${WEBHOOK_URL}"

RESULT=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")
OK=$(echo "${RESULT}" | grep -o '"ok":[^,}]*' | cut -d: -f2 | tr -d ' ')

if [[ "${OK}" == "true" ]]; then
  echo "✅ Webhook registered successfully!"
else
  echo "❌ Webhook registration failed: ${RESULT}"
  exit 1
fi

# Verify
echo ""
echo "📋 Current webhook status:"
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" \
  | python3 -c "
import json,sys
d=json.load(sys.stdin).get('result',{})
print('  URL:     ', d.get('url','none'))
print('  Pending: ', d.get('pending_update_count',0))
print('  Error:   ', d.get('last_error_message','none'))
"
