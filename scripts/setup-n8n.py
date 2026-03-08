#!/usr/bin/env python3
"""
ronkbot n8n auto-setup script.
Run this after n8n has started to ensure all workflows are imported and active.
Usage: python3 scripts/setup-n8n.py
"""

import requests
import json
import glob
import time
import sys
import os

BASE = os.environ.get("N8N_URL", "http://localhost:5678")
EMAIL = os.environ.get("N8N_OWNER_EMAIL", "")
PASSWORD = os.environ.get("N8N_BASIC_AUTH_PASSWORD", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__), "..", "n8n-workflows")

READ_ONLY_FIELDS = ["tags", "staticData", "id", "createdAt", "updatedAt"]


def wait_for_n8n():
    print("Waiting for n8n to be ready...")
    for i in range(60):
        try:
            r = requests.get(f"{BASE}/healthz", timeout=2)
            if r.status_code == 200:
                print(f"n8n is ready!")
                return True
        except:
            pass
        time.sleep(1)
    return False


def setup_owner(session):
    """Create owner account if not exists."""
    r = session.post(f"{BASE}/rest/owner/setup",
        json={"email": EMAIL, "firstName": os.environ.get("OWNER_FIRST_NAME", "Bot"), "lastName": os.environ.get("OWNER_LAST_NAME", "Owner"), "password": PASSWORD},
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    if r.status_code == 200:
        print("✅ Owner account created")
    elif r.status_code in (400, 409):
        print("  Owner account already exists")
    else:
        print(f"  Owner setup: {r.status_code}: {r.text[:100]}")


def login(session):
    """Login and return True if successful."""
    r = session.post(f"{BASE}/rest/login",
        json={"emailOrLdapLoginId": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    if r.status_code == 200:
        print(f"✅ Logged in as {EMAIL}")
        return True
    print(f"❌ Login failed: {r.status_code}: {r.text[:100]}")
    return False


def create_telegram_credential(session):
    """Create Telegram credential if not exists."""
    # Check existing
    r = session.get(f"{BASE}/rest/credentials?take=20",
        headers={"Accept": "application/json"}, timeout=5)
    if r.status_code == 200:
        existing = r.json().get("data", [])
        for cred in existing:
            if cred.get("name") == "Telegram Bot (auto)":
                print(f"  Telegram credential already exists (id={cred['id']})")
                return cred["id"]

    # Create new
    r = session.post(f"{BASE}/rest/credentials",
        json={"name": "Telegram Bot (auto)", "type": "telegramApi", 
              "data": {"accessToken": TELEGRAM_TOKEN}},
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    if r.status_code in (200, 201):
        cred_id = r.json().get("data", r.json()).get("id")
        print(f"✅ Telegram credential created (id={cred_id})")
        return cred_id
    print(f"❌ TG credential: {r.status_code}: {r.text[:200]}")
    return None


def get_workflows(session):
    """Get all existing workflows."""
    r = session.get(f"{BASE}/rest/workflows?filter=%7B%7D&skip=0&take=50",
        headers={"Accept": "application/json"}, timeout=5)
    if r.status_code != 200:
        return {}
    return {w["name"]: {"id": w["id"], "versionId": w["versionId"], "active": w["active"]}
            for w in r.json().get("data", [])}


def import_workflows(session, tg_cred_id=None):
    """Import workflow JSON files if not already imported."""
    existing = get_workflows(session)
    print(f"\nExisting workflows: {list(existing.keys())}")
    
    imported = {}
    for path in sorted(glob.glob(os.path.join(WORKFLOWS_DIR, "0[1-3]*.json"))):
        with open(path) as f:
            wf = json.load(f)
        name = wf.get("name", "")
        
        if name in existing:
            print(f"  Already exists: {name}")
            imported[name] = existing[name]
            continue
        
        # Clean read-only fields
        for k in READ_ONLY_FIELDS:
            wf.pop(k, None)
        
        # Wire Telegram credential
        if "Telegram Listener" in name and tg_cred_id:
            for node in wf.get("nodes", []):
                if "telegram" in node.get("type", "").lower():
                    node.setdefault("credentials", {})["telegramApi"] = {
                        "id": tg_cred_id, "name": "Telegram Bot (auto)"}
        
        r = session.post(f"{BASE}/rest/workflows", json=wf,
            headers={"Content-Type": "application/json"}, timeout=10)
        if r.status_code in (200, 201):
            wf_id = r.json().get("id")
            imported[name] = {"id": wf_id, "versionId": r.json().get("versionId"), "active": False}
            print(f"  ✅ Imported: {name} -> {wf_id}")
        else:
            print(f"  ❌ Failed: {name}: {r.status_code}: {r.text[:200]}")
    
    return imported


def publish_workflow(session, wf_id, version_id):
    """Publish a workflow so PATCH changes take effect in live executions.
    
    n8n has a draft/published model: PATCH via API updates the draft, but
    active executions use the last PUBLISHED version. This call promotes the
    draft to production.
    """
    r = session.post(
        f"{BASE}/rest/workflows/{wf_id}/publish",
        json={"versionId": version_id},
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    if r.status_code in (200, 204):
        print(f"  ✅ Published workflow {wf_id}")
        return True
    else:
        # Fallback: deactivate + reactivate forces n8n to reload from DB
        print(f"  ⚠️  Publish returned {r.status_code}, trying deactivate/reactivate...")
        session.post(f"{BASE}/rest/workflows/{wf_id}/deactivate", timeout=10)
        time.sleep(2)
        r2 = session.post(f"{BASE}/rest/workflows/{wf_id}/activate",
            json={"versionId": version_id},
            headers={"Content-Type": "application/json"}, timeout=15)
        if r2.status_code in (200, 204):
            print(f"  ✅ Reactivated workflow {wf_id}")
            return True
        print(f"  ❌ Could not publish/reactivate: {r2.status_code}: {r2.text[:200]}")
        return False


def activate_workflows(session, wf_map):
    """Activate workflows in dependency order."""
    # Support both old and new name for the AI Chat workflow
    for name in ["02 - AI Chat (Fallback Chain)", "02 - Gemini Chat", "03 - Command Handler", "01 - Telegram Listener"]:
        info = wf_map.get(name, {})
        wf_id = info.get("id")
        version_id = info.get("versionId")
        
        if not wf_id:
            print(f"  {name}: Not found, skipping")
            continue
        
        if info.get("active"):
            print(f"  {name}: Already active")
            continue
        
        print(f"\nActivating '{name}'...")
        r = session.post(f"{BASE}/rest/workflows/{wf_id}/activate",
            json={"versionId": version_id},
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        if r.status_code in (200, 204):
            new_vid = r.json().get("data", {}).get("versionId") or version_id
            print(f"  ✅ {name}: ACTIVE")
            # Publish so PATCH changes take effect (n8n draft/published model)
            publish_workflow(session, wf_id, new_vid)
        else:
            print(f"  ❌ {name}: HTTP {r.status_code}: {r.text[:300]}")


def main():
    if not wait_for_n8n():
        print("❌ n8n not ready after 60s")
        sys.exit(1)
    
    session = requests.Session()
    
    # Setup owner
    print("\n1. Setting up owner account...")
    setup_owner(session)
    
    # Login
    print("\n2. Logging in...")
    if not login(session):
        sys.exit(1)
    
    # Create Telegram credential
    print("\n3. Setting up Telegram credential...")
    tg_cred_id = create_telegram_credential(session)
    
    # Import workflows
    print("\n4. Importing workflows...")
    wf_map = import_workflows(session, tg_cred_id)
    
    # Activate
    print("\n5. Activating workflows...")
    activate_workflows(session, wf_map)
    
    # Final status
    print("\n=== Final Status ===")
    final = get_workflows(session)
    for name, info in final.items():
        status = "🟢 ACTIVE" if info.get("active") else "🔴 INACTIVE"
        print(f"  {status} | {name}")
    
    active_count = sum(1 for info in final.values() if info.get("active"))
    print(f"\n{active_count}/{len(final)} workflows active")


if __name__ == "__main__":
    main()
