#!/usr/bin/env python3
"""
docker-startup.py — ronkbot n8n auto-setup sidecar
Runs once after n8n becomes healthy. Handles:
  1. Owner account setup (if fresh instance — n8n 2.x setup wizard)
  2. Workflow import (if workflows missing)
  3. Workflow activation in correct dependency order
  4. Telegram webhook registration
"""
import os, json, glob, time, requests, sys

BASE  = os.environ.get("N8N_URL", "http://n8n:5678")
USER  = os.environ.get("N8N_USER", os.environ.get("N8N_OWNER_EMAIL", ""))
PASS  = os.environ.get("N8N_PASS", "")
TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
NGROK  = os.environ.get("NGROK_URL", "")
GEMINI = os.environ.get("GEMINI_API_KEY", "")
WF_DIR = "/workflows"

# Derive first/last name from OWNER_NAME (fallback to generic)
_owner_name = os.environ.get("OWNER_NAME", "Bot Owner").strip().split()
OWNER_FIRST = _owner_name[0] if _owner_name else "Bot"
OWNER_LAST  = " ".join(_owner_name[1:]) if len(_owner_name) > 1 else "Owner"

def log(msg): print(msg, flush=True)

s = requests.Session()
s.headers.update({"Content-Type": "application/json"})

# ── 1. Wait for n8n ──────────────────────────────────────────────────────────
log("⏳ Waiting for n8n to be ready...")
for i in range(1, 40):
    try:
        if requests.get(BASE + "/healthz", timeout=5).status_code == 200:
            log(f"✅ n8n healthy ({i*2}s)")
            break
    except Exception:
        pass
    time.sleep(2)
else:
    log("❌ n8n did not become healthy"); sys.exit(1)

time.sleep(5)  # Extra time for n8n internal initialization

# ── 2. Check if setup wizard is needed ───────────────────────────────────────
log("🔍 Checking n8n setup state...")
rs = requests.get(BASE + "/rest/settings", timeout=10).json().get("data", {})
needs_setup = rs.get("userManagement", {}).get("showSetupOnFirstLoad", False)
log(f"  Setup needed: {needs_setup}")

# ── 3. Complete owner setup if needed ────────────────────────────────────────
if needs_setup:
    log("🔧 Running first-time owner setup...")
    r_setup = s.post(BASE + "/rest/owner/setup", json={
        "email": USER,
        "firstName": OWNER_FIRST,
        "lastName": OWNER_LAST,
        "password": PASS,
    }, timeout=30)
    log(f"  Owner setup: {r_setup.status_code}")
    if r_setup.status_code not in (200, 201):
        log(f"  Body: {r_setup.text[:200]}")
    time.sleep(2)

# ── 4. Login ─────────────────────────────────────────────────────────────────
log("🔐 Logging in...")
r = s.post(BASE + "/rest/login", json={"emailOrLdapLoginId": USER, "password": PASS}, timeout=15)
if r.status_code == 200 and "id" in r.text:
    log("  ✅ Logged in")
else:
    log(f"  ❌ Login failed: {r.status_code} {r.text[:100]}")
    sys.exit(1)

# ── 5. Ensure Telegram credential exists ─────────────────────────────────────
log("🔑 Checking Telegram credential...")
r_creds = s.get(BASE + "/rest/credentials?filter=%7B%22type%22:%22telegramApi%22%7D", timeout=5)
tg_creds = r_creds.json().get("data", [])

if not tg_creds:
    log("  Creating telegramApi credential...")
    r_create = s.post(BASE + "/rest/credentials", json={
        "name": "Telegram Bot (auto)",
        "type": "telegramApi",
        "data": {
            "accessToken": TOKEN
        }
    }, timeout=10)
    if r_create.status_code in (200, 201):
        new_cred_id = r_create.json().get("data", r_create.json()).get("id", "?")
        log(f"  ✅ Created credential: {new_cred_id}")
        TELEGRAM_CRED_ID = new_cred_id
    else:
        log(f"  ❌ Credential creation failed: {r_create.text[:100]}")
        TELEGRAM_CRED_ID = None
else:
    TELEGRAM_CRED_ID = tg_creds[0]["id"]
    log(f"  ✅ Credential exists: {TELEGRAM_CRED_ID}")

# ── 5b. Ensure Gemini credential exists ──────────────────────────────────────
GEMINI_CRED_ID = None
if GEMINI:
    log("🔑 Checking Gemini credential...")
    r_creds2 = s.get(BASE + "/rest/credentials?filter=%7B%22type%22:%22googlePalmApi%22%7D", timeout=5)
    gm_creds = r_creds2.json().get("data", [])
    if not gm_creds:
        log("  Creating googlePalmApi credential...")
        r_gm = s.post(BASE + "/rest/credentials", json={
            "name": "Google Gemini (auto)",
            "type": "googlePalmApi",
            "data": {"apiKey": GEMINI}
        }, timeout=10)
        if r_gm.status_code in (200, 201):
            GEMINI_CRED_ID = r_gm.json().get("data", r_gm.json()).get("id", "?")
            log(f"  ✅ Created Gemini credential: {GEMINI_CRED_ID}")
        else:
            log(f"  ❌ Gemini credential creation failed: {r_gm.text[:100]}")
    else:
        GEMINI_CRED_ID = gm_creds[0]["id"]
        log(f"  ✅ Gemini credential exists: {GEMINI_CRED_ID}")
else:
    log("⚠️  GEMINI_API_KEY not set — skipping Gemini credential")


r = s.get(BASE + "/rest/workflows?filter=%7B%7D&skip=0&take=20", timeout=5)
existing = r.json().get("data", [])
active_names = [w["name"] for w in existing if w.get("active")]
log(f"📋 Workflows: {len(existing)} total, {len(active_names)} active")
listener_active = any("Telegram Listener" in n for n in active_names)

# ── 6. Import & activate workflows if needed ─────────────────────────────────
ids = {w["name"]: w["id"] for w in existing}

if not listener_active:
    log("📥 Importing/activating workflows...")

    # Import any missing workflows
    for fpath in sorted(glob.glob(WF_DIR + "/0[1-7]*.json")):
        with open(fpath) as f:
            wf = json.load(f)
        name = wf.get("name", "?")
        if name in ids:
            log(f"  ⏭️  {name} already exists")
            continue
        for k in ["id", "versionId", "createdAt", "updatedAt"]:
            wf.pop(k, None)
        wf["active"] = False
        ri = s.post(BASE + "/rest/workflows", json=wf, timeout=10)
        if ri.status_code in (200, 201):
            new_id = ri.json().get("data", ri.json()).get("id", "?")
            ids[name] = new_id
            log(f"  ✅ Imported: {name} → {new_id}")
        else:
            log(f"  ❌ Import failed: {name}: {ri.text[:80]}")

    ai_id  = ids.get("02 - AI Chat (Fallback Chain)")
    cmd_id = ids.get("03 - Command Handler")
    lst_id = ids.get("01 - Telegram Listener")

    # Fix Execute Workflow refs in 01-Listener so they use current IDs
    # AND update Telegram credential IDs to the new/existing credential
    if lst_id:
        r2 = s.get(BASE + "/rest/workflows/" + lst_id, timeout=5)
        wf01 = r2.json().get("data", r2.json())
        changed = False
        for node in wf01.get("nodes", []):
            # Fix Execute Workflow refs
            if ai_id and "Execute AI" in node.get("name", ""):
                node["parameters"]["workflowId"] = ai_id
                node["typeVersion"] = 1
                node["parameters"].pop("source", None)
                changed = True
            if cmd_id and "Execute Command" in node.get("name", ""):
                node["parameters"]["workflowId"] = cmd_id
                node["typeVersion"] = 1
                node["parameters"].pop("source", None)
                changed = True
            # Fix Telegram credential IDs on any Telegram node
            if TELEGRAM_CRED_ID and node.get("type","").startswith("n8n-nodes-base.telegram"):
                for cred_type, cred_info in node.get("credentials", {}).items():
                    if cred_type == "telegramApi":
                        if cred_info.get("id") != TELEGRAM_CRED_ID:
                            cred_info["id"] = TELEGRAM_CRED_ID
                            cred_info["name"] = "Telegram Bot (auto)"
                            changed = True
        if changed:
            patch_r = s.patch(BASE + "/rest/workflows/" + lst_id, json=wf01, timeout=10)
            log(f"  🔧 Fixed Execute refs + credential IDs in 01-Listener ({patch_r.status_code})")

    # Fix Gemini credential ID in 02-AI Chat workflow
    if ai_id and GEMINI_CRED_ID:
        r_ai = s.get(BASE + "/rest/workflows/" + ai_id, timeout=5)
        wf02 = r_ai.json().get("data", r_ai.json())
        changed2 = False
        for node in wf02.get("nodes", []):
            for cred_type, cred_info in node.get("credentials", {}).items():
                if cred_type == "googlePalmApi":
                    if cred_info.get("id") != GEMINI_CRED_ID:
                        cred_info["id"] = GEMINI_CRED_ID
                        cred_info["name"] = "Google Gemini (auto)"
                        changed2 = True
        if changed2:
            patch_r2 = s.patch(BASE + "/rest/workflows/" + ai_id, json=wf02, timeout=10)
            log(f"  🔧 Wired Gemini credential into 02-AI Chat ({patch_r2.status_code})")

    # Activate in dependency order: leaf → root
    ACTIVATE_ORDER = [
        "05 - Email Reader",
        "06 - Email Sender",
        "07 - Writing Style Analyzer",
        "02 - AI Chat (Fallback Chain)",
        "03 - Command Handler",
        "01 - Telegram Listener",
    ]
    for name in ACTIVATE_ORDER:
        wid = ids.get(name)
        if not wid:
            continue
        r3 = s.get(BASE + "/rest/workflows/" + wid, timeout=5)
        vid = r3.json().get("data", r3.json()).get("versionId")
        ra = s.post(BASE + "/rest/workflows/" + wid + "/activate",
                    json={"versionId": vid}, timeout=60)
        icon = "✅" if ra.status_code == 200 else "⚠️"
        log(f"  {icon} Activate {name[:44]}: {ra.status_code}")

        # Special handling for Telegram Listener: if it fails because cmd handler
        # isn't published, temporarily disconnect it so AI chat still works
        if ra.status_code != 200 and "Telegram Listener" in name:
            err = ra.text
            if "not published" in err or "references workflow" in err:
                log("  🔧 Listener blocked by unpublished deps — activating in AI-only mode...")
                r4 = s.get(BASE + "/rest/workflows/" + wid, timeout=5)
                wf_fix = r4.json().get("data", r4.json())
                # Remove connections from Is Command? node to Execute Command Handler
                conns = wf_fix.get("connections", {})
                for src_node, outputs in list(conns.items()):
                    if "Is Command" in src_node or "Command" in src_node:
                        for output_list in outputs.get("main", []):
                            output_list[:] = [
                                c for c in output_list
                                if "Command Handler" not in c.get("node", "")
                            ]
                # Also remove Execute Command Handler node entirely
                wf_fix["nodes"] = [
                    n for n in wf_fix.get("nodes", [])
                    if "Execute Command Handler" not in n.get("name", "")
                ]
                s.patch(BASE + "/rest/workflows/" + wid, json=wf_fix, timeout=10)
                r5 = s.get(BASE + "/rest/workflows/" + wid, timeout=5)
                vid2 = r5.json().get("data", r5.json()).get("versionId")
                ra2 = s.post(BASE + "/rest/workflows/" + wid + "/activate",
                             json={"versionId": vid2}, timeout=60)
                if ra2.status_code == 200:
                    log("  ✅ Listener activated in AI-only mode (commands disabled until email workflows install)")
                else:
                    log(f"  ❌ Listener still failed: {ra2.text[:120]}")
        time.sleep(0.8)
else:
    log("✅ Telegram Listener already active — skipping import")

# ── 7. Register Telegram webhook ─────────────────────────────────────────────
if TOKEN and NGROK:
    webhook_url = f"{NGROK}/webhook/telegram-bot-webhook"
    log(f"🔗 Registering Telegram webhook → {webhook_url}")
    r = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}",
        timeout=15
    )
    result = r.json()
    log(f"  {'✅' if result.get('ok') else '❌'} {result.get('description', result)}")
else:
    log("⚠️  TOKEN or NGROK_URL not set — skipping webhook")

log(f"\n✅ ronkbot startup complete: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
