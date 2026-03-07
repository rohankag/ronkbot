#!/usr/bin/env bash
# ============================================================
# ronkbot-startup.sh
# Auto-recovery script: re-imports, activates workflows, and
# registers the Telegram webhook after every Docker restart.
#
# Run via: docker exec ronkbot-n8n bash /tmp/ronkbot-startup.sh
# Or mount as a sidecar in docker-compose.yml
# ============================================================
set -euo pipefail

N8N_URL="${N8N_URL:-http://localhost:5678}"
N8N_USER="${N8N_BASIC_AUTH_USER:-}"
N8N_PASS="${N8N_BASIC_AUTH_PASSWORD:-}"
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
NGROK="${NGROK_URL:-}"
WF_DIR="${WF_DIR:-/Users/rohankagarwal/coding/LC/projects/ronkbot/n8n-workflows}"

echo "🚀 ronkbot startup: $(date)"

# 1. Wait for n8n to be up
echo "⏳ Waiting for n8n..."
for i in $(seq 1 30); do
  if curl -sf "${N8N_URL}/healthz" > /dev/null 2>&1; then
    echo "✅ n8n is up (${i}s)"
    break
  fi
  sleep 2
done

# 2. Login
echo "🔐 Logging in..."
LOGIN_RESP=$(curl -sf -X POST "${N8N_URL}/rest/login" \
  -H "Content-Type: application/json" \
  -d "{\"emailOrLdapLoginId\":\"${N8N_USER}\",\"password\":\"${N8N_PASS}\"}" \
  -c /tmp/n8n-cookies.txt -b /tmp/n8n-cookies.txt 2>&1 || echo "FAIL")

if echo "${LOGIN_RESP}" | grep -q '"id"'; then
  echo "  ✅ Logged in"
else
  echo "  ⚠️  Login failed. Trying owner setup..."
  # Attempt owner setup (fresh instance)
  curl -sf -X POST "${N8N_URL}/rest/owner-setup" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${N8N_USER}\",\"firstName\":\"Rohan\",\"lastName\":\"Agarwal\",\"password\":\"${N8N_PASS}\"}" \
    -c /tmp/n8n-cookies.txt -b /tmp/n8n-cookies.txt > /dev/null 2>&1 || true
  # Re-login
  curl -sf -X POST "${N8N_URL}/rest/login" \
    -H "Content-Type: application/json" \
    -d "{\"emailOrLdapLoginId\":\"${N8N_USER}\",\"password\":\"${N8N_PASS}\"}" \
    -c /tmp/n8n-cookies.txt -b /tmp/n8n-cookies.txt > /dev/null 2>&1 || true
  echo "  Re-login attempted"
fi

# 3. Check how many workflows exist
WF_COUNT=$(curl -sf "${N8N_URL}/rest/workflows?filter=%7B%7D&skip=0&take=1" \
  -b /tmp/n8n-cookies.txt | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('count',0))" 2>/dev/null || echo "0")
echo "📋 Current workflow count: ${WF_COUNT}"

# 4. Import workflows if needed
if [ "${WF_COUNT:-0}" -lt 3 ]; then
  echo "📥 Importing workflows..."
  python3 << PYEOF
import requests, json, os, glob, time, sys

BASE = "${N8N_URL}"
s = requests.Session()
s.headers.update({"Content-Type": "application/json"})
# Load cookies
import http.cookiejar
jar = http.cookiejar.MozillaCookieJar("/tmp/n8n-cookies.txt")
try:
    jar.load()
    s.cookies = jar
except:
    pass
s.post(BASE + "/rest/login", json={"emailOrLdapLoginId":"${N8N_USER}","password":"${N8N_PASS}"}, timeout=10)

WF_DIR = "${WF_DIR}"
files = sorted(glob.glob(WF_DIR + "/0[1-7]*.json"))
imported_ids = {}

for fpath in files:
    with open(fpath) as f:
        wf = json.load(f)
    name = wf.get("name","?")
    for k in ["id","versionId","createdAt","updatedAt"]:
        wf.pop(k, None)
    wf["active"] = False
    ri = s.post(BASE + "/rest/workflows", json=wf, timeout=10)
    if ri.status_code in (200,201):
        new_id = ri.json().get("data",ri.json()).get("id","?")
        imported_ids[name] = new_id
        print(f"  ✅ {name} → {new_id}")
    else:
        print(f"  ❌ {name}: {ri.text[:80]}")

ai_id  = imported_ids.get("02 - AI Chat (Fallback Chain)")
cmd_id = imported_ids.get("03 - Command Handler")
lst_id = imported_ids.get("01 - Telegram Listener")

# Fix Execute refs in listener
if lst_id and ai_id and cmd_id:
    r2 = s.get(BASE + "/rest/workflows/" + lst_id, timeout=5)
    wf01 = r2.json().get("data", r2.json())
    for node in wf01.get("nodes",[]):
        if "Execute Command" in node.get("name",""):
            node["parameters"]["workflowId"] = cmd_id
        if "Execute AI" in node.get("name",""):
            node["parameters"]["workflowId"] = ai_id
    s.patch(BASE + "/rest/workflows/" + lst_id, json=wf01, timeout=10)
    print("  🔧 Fixed Execute refs in Listener")

# Activate: 02 first, then 01
for name, wid in imported_ids.items():
    if "01 - Telegram" in name:
        continue
    r3 = s.get(BASE + "/rest/workflows/" + wid, timeout=5)
    vid = r3.json().get("data",r3.json()).get("versionId")
    ra = s.post(BASE + "/rest/workflows/" + wid + "/activate", json={"versionId":vid}, timeout=60)
    print(f"  {'✅' if ra.status_code==200 else '⚠️'} Activate {name[:40]}: {ra.status_code}")
    time.sleep(0.5)

if lst_id:
    time.sleep(2)
    r4 = s.get(BASE + "/rest/workflows/" + lst_id, timeout=5)
    vid = r4.json().get("data",r4.json()).get("versionId")
    ra = s.post(BASE + "/rest/workflows/" + lst_id + "/activate", json={"versionId":vid}, timeout=60)
    print(f"  {'✅' if ra.status_code==200 else '⚠️'} Activate 01-Listener: {ra.status_code}")

PYEOF
else
  echo "✅ Workflows already present (count: ${WF_COUNT})"
fi

# 5. Set Telegram webhook
if [ -n "${BOT_TOKEN}" ] && [ -n "${NGROK}" ]; then
  WEBHOOK_URL="${NGROK}/webhook/telegram-bot-webhook"
  echo "🔗 Setting Telegram webhook → ${WEBHOOK_URL}"
  RESULT=$(curl -sf "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")
  echo "   ${RESULT}"
fi

echo ""
echo "✅ ronkbot startup complete: $(date)"
