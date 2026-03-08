#!/usr/bin/env python3
"""
watchdog.py — Self-healing watchdog for ronkbot
Monitors n8n webhook health and auto-recovers from failures.
Runs as a daemon thread inside the mac-agent.
"""
import os
import time
import logging
import threading
import subprocess
import requests

log = logging.getLogger("mac-agent.watchdog")

# ── Config ───────────────────────────────────────────────────────────────────
N8N_URL           = os.environ.get("N8N_URL", "http://localhost:5678")
N8N_EMAIL         = os.environ.get("N8N_OWNER_EMAIL", "")
N8N_PASS          = os.environ.get("N8N_BASIC_AUTH_PASSWORD", "")
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
NGROK_URL         = os.environ.get("NGROK_URL", "")
WEBHOOK_PATH      = "telegram-bot-webhook"

CHECK_INTERVAL    = 60      # seconds between checks
HEAL_COOLDOWN     = 300     # seconds between heal attempts (5 min)
STARTUP_DELAY     = 30      # seconds to wait before first check

# ── State ────────────────────────────────────────────────────────────────────
_state = {
    "n8n_healthy": False,
    "webhook_healthy": False,
    "last_check": None,
    "last_heal": None,
    "last_heal_result": None,
    "heal_count": 0,
    "consecutive_failures": 0,
}
_state_lock = threading.Lock()


def get_state() -> dict:
    """Return a copy of the current watchdog state."""
    with _state_lock:
        return dict(_state)


def _update_state(**kwargs):
    with _state_lock:
        _state.update(kwargs)


# ── Health Checks ────────────────────────────────────────────────────────────
def check_n8n_health() -> bool:
    """Check if n8n is responding to healthz."""
    try:
        r = requests.get(f"{N8N_URL}/healthz", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def check_webhook_health() -> bool:
    """Check if the Telegram webhook endpoint is registered in n8n.
    A registered webhook returns 200 on POST (even with bad data).
    An unregistered webhook returns 404.
    """
    try:
        r = requests.post(
            f"{N8N_URL}/webhook/{WEBHOOK_PATH}",
            json={"message": {"message_id": 0, "from": {"id": 0, "username": "__healthcheck__"},
                              "chat": {"id": 0, "type": "private"}, "date": 0, "text": ""}},
            timeout=5,
        )
        # 200 = webhook registered and workflow ran (or started)
        # 404 = webhook not registered
        return r.status_code != 404
    except Exception:
        return False


# ── Heal Actions ─────────────────────────────────────────────────────────────
def _n8n_login() -> requests.Session | None:
    """Login to n8n REST API and return an authenticated session."""
    if not N8N_PASS:
        log.warning("watchdog: N8N_BASIC_AUTH_PASSWORD not set, cannot heal")
        return None
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    try:
        r = s.post(f"{N8N_URL}/rest/login", json={
            "emailOrLdapLoginId": N8N_EMAIL,
            "password": N8N_PASS,
        }, timeout=10)
        if r.status_code == 200 and "id" in r.text:
            return s
        log.error("watchdog: n8n login failed: %s %s", r.status_code, r.text[:100])
    except Exception as e:
        log.error("watchdog: n8n login error: %s", e)
    return None


def _find_listener_workflow(session: requests.Session) -> tuple[str | None, str | None]:
    """Find the Telegram Listener workflow and return (workflow_id, version_id)."""
    try:
        r = session.get(f"{N8N_URL}/rest/workflows?filter=%7B%7D&skip=0&take=20", timeout=5)
        for wf in r.json().get("data", []):
            if "Telegram Listener" in wf.get("name", ""):
                wid = wf["id"]
                # Get full workflow to get versionId
                r2 = session.get(f"{N8N_URL}/rest/workflows/{wid}", timeout=5)
                vid = r2.json().get("data", r2.json()).get("versionId")
                return wid, vid
    except Exception as e:
        log.error("watchdog: error finding listener workflow: %s", e)
    return None, None


def heal_webhook() -> bool:
    """Auto-heal the webhook by toggling the Telegram Listener workflow."""
    log.info("🔧 watchdog: attempting webhook heal...")

    session = _n8n_login()
    if not session:
        return False

    wid, vid = _find_listener_workflow(session)
    if not wid:
        log.error("watchdog: could not find Telegram Listener workflow")
        return False

    try:
        # Step 1: Deactivate
        log.info("watchdog: deactivating workflow %s...", wid)
        r = session.post(f"{N8N_URL}/rest/workflows/{wid}/deactivate", timeout=10)
        if r.status_code != 200:
            log.warning("watchdog: deactivate returned %s (may already be inactive)", r.status_code)
        time.sleep(2)

        # Step 2: Get fresh versionId after deactivation
        r2 = session.get(f"{N8N_URL}/rest/workflows/{wid}", timeout=5)
        vid = r2.json().get("data", r2.json()).get("versionId")

        # Step 3: Re-activate
        log.info("watchdog: re-activating workflow %s...", wid)
        ra = session.post(f"{N8N_URL}/rest/workflows/{wid}/activate",
                          json={"versionId": vid}, timeout=60)
        if ra.status_code != 200:
            log.error("watchdog: activation failed: %s %s", ra.status_code, ra.text[:200])
            return False

        # Step 4: Re-register Telegram webhook
        if TELEGRAM_TOKEN and NGROK_URL:
            webhook_url = f"{NGROK_URL}/webhook/{WEBHOOK_PATH}"
            log.info("watchdog: registering Telegram webhook → %s", webhook_url)
            rt = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}",
                timeout=15,
            )
            result = rt.json()
            if not result.get("ok"):
                log.error("watchdog: Telegram webhook registration failed: %s", result)
                return False

        log.info("✅ watchdog: webhook healed successfully!")
        return True

    except Exception as e:
        log.error("watchdog: heal error: %s", e)
        return False


def heal_n8n() -> bool:
    """Attempt to restart the n8n Docker container."""
    log.info("🔧 watchdog: attempting n8n restart...")
    try:
        result = subprocess.run(
            ["docker", "restart", "ronkbot-n8n"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            log.info("✅ watchdog: n8n container restarted")
            # Wait for it to become healthy
            for _ in range(12):
                time.sleep(5)
                if check_n8n_health():
                    return True
            log.warning("watchdog: n8n restarted but still not healthy")
        else:
            log.error("watchdog: docker restart failed: %s", result.stderr[:200])
    except Exception as e:
        log.error("watchdog: restart error: %s", e)
    return False


def _send_notification(message: str):
    """Send a macOS notification about the heal event."""
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "🤖 ronkbot"'],
            timeout=5, capture_output=True,
        )
    except Exception:
        pass  # Best-effort


# ── Main Loop ────────────────────────────────────────────────────────────────
def run_watchdog_loop(interval: int = CHECK_INTERVAL):
    """Main watchdog loop. Runs forever as a daemon thread."""
    log.info("🐕 Watchdog started (interval=%ds, cooldown=%ds)", interval, HEAL_COOLDOWN)

    # Wait for initial startup
    time.sleep(STARTUP_DELAY)

    while True:
        try:
            now = time.strftime("%Y-%m-%dT%H:%M:%S")

            # Check n8n health
            n8n_ok = check_n8n_health()
            _update_state(n8n_healthy=n8n_ok, last_check=now)

            if not n8n_ok:
                log.warning("watchdog: n8n is DOWN")
                _update_state(webhook_healthy=False, consecutive_failures=_state["consecutive_failures"] + 1)

                # Only try to restart if cooldown has passed
                last_heal = _state.get("last_heal")
                if last_heal is None or (time.time() - time.mktime(time.strptime(last_heal, "%Y-%m-%dT%H:%M:%S"))) > HEAL_COOLDOWN:
                    healed = heal_n8n()
                    _update_state(
                        last_heal=now,
                        last_heal_result="n8n_restart_" + ("ok" if healed else "failed"),
                        heal_count=_state["heal_count"] + 1,
                    )
                    if healed:
                        _send_notification("n8n was down — restarted container")
                        _update_state(consecutive_failures=0)
                        # After n8n restart, give it time then check webhook
                        time.sleep(10)
                        if not check_webhook_health():
                            heal_webhook()
                else:
                    log.info("watchdog: in cooldown, skipping n8n heal")

                time.sleep(interval)
                continue

            # n8n is up — check webhook
            webhook_ok = check_webhook_health()
            _update_state(webhook_healthy=webhook_ok)

            if webhook_ok:
                if _state["consecutive_failures"] > 0:
                    log.info("watchdog: recovered after %d failures", _state["consecutive_failures"])
                _update_state(consecutive_failures=0)
            else:
                failures = _state["consecutive_failures"] + 1
                _update_state(consecutive_failures=failures)
                log.warning("watchdog: webhook is DOWN (failure #%d)", failures)

                # Only heal if cooldown has passed
                last_heal = _state.get("last_heal")
                cooldown_ok = last_heal is None or (time.time() - time.mktime(time.strptime(last_heal, "%Y-%m-%dT%H:%M:%S"))) > HEAL_COOLDOWN
                if cooldown_ok:
                    healed = heal_webhook()
                    _update_state(
                        last_heal=now,
                        last_heal_result="webhook_heal_" + ("ok" if healed else "failed"),
                        heal_count=_state["heal_count"] + 1,
                    )
                    if healed:
                        _send_notification("Webhook was dead — auto-healed")
                        _update_state(consecutive_failures=0, webhook_healthy=True)
                else:
                    log.info("watchdog: in cooldown, skipping webhook heal")

        except Exception as e:
            log.error("watchdog: loop error: %s", e)

        time.sleep(interval)


def start_watchdog():
    """Start the watchdog as a daemon thread."""
    t = threading.Thread(target=run_watchdog_loop, daemon=True, name="ronkbot-watchdog")
    t.start()
    return t
