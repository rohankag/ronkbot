#!/bin/bash
# start-ronkbot.sh - Start ronkbot with ngrok HTTPS tunnel and full n8n setup
# Auto-run: registered as macOS LaunchAgent (com.ronkbot.startup)
# Usage: ./scripts/start-ronkbot.sh

set -e

# Wait for Docker Desktop to fully start (needed when run at login)
echo "⏳ Waiting 30s for Docker to initialize..."
sleep 30

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🤖 Starting ronkbot..."
cd "$PROJECT_DIR"

# 1. Start ngrok tunnel
echo "📡 Starting ngrok tunnel..."
pkill -f "ngrok" 2>/dev/null || true
sleep 1
/opt/homebrew/bin/ngrok http 5678 --log=stdout > /tmp/ngrok-ronkbot.log 2>&1 &
NGROK_PID=$!
echo "  ngrok PID: $NGROK_PID"

# Wait for tunnel URL
echo "  Waiting for tunnel URL..."
NGROK_URL=""
for _ in $(seq 1 20); do
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)  
    for t in d.get('tunnels',[]):
        u=t.get('public_url','')
        if u.startswith('https'):
            print(u)
            break
except: pass
" 2>/dev/null)
    if [ -n "$NGROK_URL" ]; then
        echo "  ✅ Tunnel: $NGROK_URL"
        break
    fi
    sleep 1
done

if [ -z "$NGROK_URL" ]; then
    echo "  ⚠️  Could not get ngrok URL - using localhost (Telegram webhook won't work)"
    NGROK_URL="http://localhost:5678"
fi

# 2. Update WEBHOOK_URL in docker-compose
echo "🔧 Updating WEBHOOK_URL..."
sed -i.bak "s|WEBHOOK_URL=.*|WEBHOOK_URL=${NGROK_URL}/|g" docker-compose.yml
echo "  WEBHOOK_URL=${NGROK_URL}/"

# 3. Start n8n
echo "🐳 Starting n8n Docker container..."
docker compose down 2>/dev/null || true
docker compose up -d
echo "  Waiting for n8n to be ready..."
sleep 20

# 4. Run full setup + activation
echo "⚙️  Running full n8n setup and activation..."
python3 << 'PYEOF'
import requests, json, time, glob

BASE = "http://localhost:5678"
s = requests.Session()
s.headers.update({"Content-Type": "application/json"})

# Wait for n8n
for i in range(30):
    try:
        if requests.get(f"{BASE}/healthz", timeout=2).status_code == 200:
            break
    except: pass
    time.sleep(1)

# Setup owner
n8n_email = os.environ.get('N8N_OWNER_EMAIL', '')
n8n_pass = os.environ.get('N8N_BASIC_AUTH_PASSWORD', '')
tg_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
owner_name = os.environ.get('OWNER_NAME', 'Owner').split(' ', 1)
first_name = owner_name[0]
last_name = owner_name[1] if len(owner_name) > 1 else ''

s.post(f"{BASE}/rest/owner/setup", json={
    "email": n8n_email,
    "firstName": first_name, "lastName": last_name,
    "password": n8n_pass
}, timeout=10)

# Login
s.post(f"{BASE}/rest/login", json={
    "emailOrLdapLoginId": n8n_email,
    "password": n8n_pass
}, timeout=10)

# Create Telegram credential
r = s.post(f"{BASE}/rest/credentials", json={
    "name": "ronku_bot", "type": "telegramApi",
    "data": {"accessToken": tg_token}
}, timeout=10)
tg_cred_id = (r.json().get("data") or r.json()).get("id")
print(f"Telegram cred: {tg_cred_id}")

# Import workflows in order: 02, 03, then 01
SKIP_FIELDS = ["id", "tags", "staticData", "createdAt", "updatedAt"]
EMAIL_NODES = {"Check Emails","Read Email","Reply Email","Send Email","Search Emails",
               "Parse Email Subcommand","Route Email Subcommand","Email Auth Message"}

imported_ids = {}
def get_wfs():
    r = s.get(f"{BASE}/rest/workflows?filter=%7B%7D&skip=0&take=100", timeout=5)
    return r.json().get("data", [])

def get_active_id(name):
    for w in get_wfs():
        if w["name"] == name and w.get("active"): return w["id"]
    for w in get_wfs():
        if w["name"] == name: return w["id"]
    return None

def activate_wf(wf_id):
    for w in get_wfs():
        if w["id"] == wf_id:
            ra = s.post(f"{BASE}/rest/workflows/{wf_id}/activate", 
                       json={"versionId": w.get("versionId")}, timeout=60)
            return ra.status_code
    return None

# Import 02 - AI Chat (Fallback Chain) — inject real API keys from .env
import os, re

def load_env(path):
    vals = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                vals[k.strip()] = v.strip()
    return vals

project_dir = os.environ.get('PROJECT_DIR', os.path.dirname(os.path.dirname(os.path.abspath('.'))))
env_path = os.path.join(project_dir, '.env')
env = load_env(env_path)

wf_dir = os.path.join(project_dir, 'n8n-workflows')
with open(os.path.join(wf_dir, '02-gemini-chat.json')) as f:
    wf02 = json.load(f)
for k in SKIP_FIELDS: wf02.pop(k, None)
wf02.setdefault("settings", {})["callerPolicy"] = "any"

# Inject actual keys from .env into the AI Fallback Chain Code node
for node in wf02.get("nodes", []):
    if node.get("name") == "AI Fallback Chain":
        code = node["parameters"]["jsCode"]
        code = code.replace("'__GITHUB_TOKEN__'", f"'{env.get('GITHUB_TOKEN','ghp_PLACEHOLDER')}'")
        code = code.replace("'__GROQ_API_KEY__'", f"'{env.get('GROQ_API_KEY','gsk_PLACEHOLDER')}'")
        code = code.replace("'__GEMINI_API_KEY__'", f"'{env.get('GEMINI_API_KEY','')}'")
        code = code.replace("'__OPENROUTER_API_KEY__'", f"'{env.get('OPENROUTER_API_KEY','sk-or-PLACEHOLDER')}'")
        node["parameters"]["jsCode"] = code
        active = [p for p in ['GITHUB_TOKEN','GROQ_API_KEY','GEMINI_API_KEY','OPENROUTER_API_KEY']
                  if 'PLACEHOLDER' not in env.get(p,'PLACEHOLDER') and env.get(p,'')]
        print(f"AI providers active: {active}")
    # Wire Telegram credential
    if "telegramApi" in node.get("credentials", {}) and tg_cred_id:
        node["credentials"]["telegramApi"] = {"id": tg_cred_id, "name": "ronku_bot"}

r2 = s.post(f"{BASE}/rest/workflows", json=wf02, timeout=10)
id_02 = (r2.json().get("data") or r2.json()).get("id")
print(f"02 imported: {id_02}")
if id_02: print(f"  activate: {activate_wf(id_02)}")

# Import 03 - Command Handler (without email nodes)
with open(os.path.join(wf_dir, '03-command-handler.json')) as f:
    wf03 = json.load(f)
for k in SKIP_FIELDS: wf03.pop(k, None)
wf03.setdefault("settings", {})["callerPolicy"] = "any"
# Remove email nodes
keep = [n for n in wf03.get("nodes", []) if n["name"] not in EMAIL_NODES]
kn = {n["name"] for n in keep}
wf03["nodes"] = keep
wf03["connections"] = {k:{pt:[[c for c in o if c.get("node") in kn] for o in outs]
    for pt,outs in d.items()} for k,d in wf03.get("connections",{}).items() if k in kn}
r3 = s.post(f"{BASE}/rest/workflows", json=wf03, timeout=10)
id_03 = (r3.json().get("data") or r3.json()).get("id")
print(f"03 imported: {id_03}")
if id_03: print(f"  activate: {activate_wf(id_03)}")

# Create stubs for 05 and 06
for sn in ["05 - Email Reader", "06 - Email Sender"]:
    stub = {"name": sn, "nodes": [
        {"name": "Execute Workflow Trigger", "type": "n8n-nodes-base.executeWorkflowTrigger",
         "typeVersion": 1, "position": [300, 300], "parameters": {}}
    ], "connections": {}, "settings": {"callerPolicy": "any"}}
    rs = s.post(f"{BASE}/rest/workflows", json=stub, timeout=10)
    d = rs.json().get("data") or rs.json()
    stub_id = d.get("id")
    if stub_id: activate_wf(stub_id)
    print(f"{sn} stub: {stub_id}")

# Import 01 - Telegram Listener (with corrected IDs)
with open(os.path.join(wf_dir, '01-telegram-listener.json')) as f:
    wf01 = json.load(f)
for k in SKIP_FIELDS: wf01.pop(k, None)
wf01.setdefault("settings", {})["callerPolicy"] = "any"

# Inject correct workflow IDs and Telegram credential
for node in wf01.get("nodes", []):
    t = node.get("type", "")
    nm = node.get("name", "")
    params = node.get("parameters", {})
    
    # Replace placeholders with real IDs
    if "executeWorkflow" in t:
        wref = params.get("workflowId", "")
        if "__WORKFLOW_03_ID__" in str(wref) or "Execute Command Handler" in nm:
            params["workflowId"] = id_03
        elif "__WORKFLOW_02_ID__" in str(wref) or "Execute Gemini" in nm:
            params["workflowId"] = id_02
    
    # Wire Telegram credential
    if "telegramTrigger" in t and tg_cred_id:
        node.setdefault("credentials", {})["telegramApi"] = {"id": tg_cred_id, "name": "ronku_bot"}

r1 = s.post(f"{BASE}/rest/workflows", json=wf01, timeout=10)
id_01 = (r1.json().get("data") or r1.json()).get("id")
print(f"01 imported: {id_01}")
if id_01: 
    status = activate_wf(id_01)
    print(f"  activate: {status}")

# Final status
print("\n=== Final Status ===")
seen = {}
for w in get_wfs():
    nm = w["name"]
    if nm not in seen or w["active"]:
        seen[nm] = w
for nm, w in seen.items():
    icon = "🟢 ACTIVE" if w["active"] else "🔴 INACTIVE"
    print(f"  {icon} | {nm}")

active_count = sum(1 for w in seen.values() if w["active"])
print(f"\n{active_count}/{len(seen)} workflows active")
PYEOF

echo ""
echo "✅ ronkbot is running!"
echo "   n8n UI: http://localhost:5678"
echo "   Tunnel: $NGROK_URL"
echo "   Bot: @ronku_bot"
echo ""
echo "Send /help to @ronku_bot on Telegram to test."
