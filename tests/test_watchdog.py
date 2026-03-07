#!/usr/bin/env python3
"""
test_watchdog.py — Unit tests for the self-healing watchdog module.
"""
import sys
import os
import time
from unittest.mock import patch, MagicMock

import pytest

# Add the mac-agent directory to path so we can import watchdog
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "mac-agent"))
import watchdog


# ── check_n8n_health ─────────────────────────────────────────────────────────

class TestCheckN8nHealth:
    @patch("watchdog.requests.get")
    def test_healthy(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        assert watchdog.check_n8n_health() is True
        mock_get.assert_called_once()

    @patch("watchdog.requests.get")
    def test_unhealthy_status(self, mock_get):
        mock_get.return_value = MagicMock(status_code=503)
        assert watchdog.check_n8n_health() is False

    @patch("watchdog.requests.get", side_effect=ConnectionError("refused"))
    def test_connection_error(self, mock_get):
        assert watchdog.check_n8n_health() is False


# ── check_webhook_health ─────────────────────────────────────────────────────

class TestCheckWebhookHealth:
    @patch("watchdog.requests.post")
    def test_webhook_registered(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        assert watchdog.check_webhook_health() is True

    @patch("watchdog.requests.post")
    def test_webhook_not_registered(self, mock_post):
        mock_post.return_value = MagicMock(status_code=404)
        assert watchdog.check_webhook_health() is False

    @patch("watchdog.requests.post")
    def test_webhook_500_still_registered(self, mock_post):
        # 500 means the workflow errored but IS registered
        mock_post.return_value = MagicMock(status_code=500)
        assert watchdog.check_webhook_health() is True

    @patch("watchdog.requests.post", side_effect=ConnectionError("refused"))
    def test_connection_error(self, mock_post):
        assert watchdog.check_webhook_health() is False


# ── heal_webhook ─────────────────────────────────────────────────────────────

class TestHealWebhook:
    @patch("watchdog.N8N_PASS", "testpass")
    @patch("watchdog.TELEGRAM_TOKEN", "test-token")
    @patch("watchdog.NGROK_URL", "https://test.ngrok.io")
    @patch("watchdog.requests")
    def test_successful_heal(self, mock_requests_mod):
        # Mock session
        mock_session = MagicMock()
        mock_requests_mod.Session.return_value = mock_session

        # Login success
        mock_session.post.return_value = MagicMock(status_code=200, text='{"id": "123"}')
        # List workflows
        mock_session.get.side_effect = [
            # GET /rest/workflows — list
            MagicMock(json=lambda: {"data": [
                {"id": "wf1", "name": "01 - Telegram Listener", "active": True}
            ]}),
            # GET /rest/workflows/wf1 — get version
            MagicMock(json=lambda: {"data": {"versionId": "v1"}}),
            # GET after deactivate — fresh version
            MagicMock(json=lambda: {"data": {"versionId": "v2"}}),
        ]

        # Mock POST calls: login, deactivate, activate
        def post_side_effect(url, **kwargs):
            if "login" in url:
                return MagicMock(status_code=200, text='{"id": "123"}')
            elif "deactivate" in url:
                return MagicMock(status_code=200)
            elif "activate" in url:
                return MagicMock(status_code=200)
            return MagicMock(status_code=200)

        mock_session.post.side_effect = post_side_effect

        # Mock Telegram setWebhook
        mock_requests_mod.get.return_value = MagicMock(
            json=lambda: {"ok": True, "description": "Webhook was set"}
        )

        result = watchdog.heal_webhook()
        assert result is True

    @patch("watchdog.N8N_PASS", "")
    def test_heal_no_password(self):
        """Should fail gracefully if no n8n password is set."""
        result = watchdog.heal_webhook()
        assert result is False


# ── get_state ────────────────────────────────────────────────────────────────

class TestGetState:
    def test_initial_state(self):
        state = watchdog.get_state()
        assert "n8n_healthy" in state
        assert "webhook_healthy" in state
        assert "heal_count" in state

    def test_update_state(self):
        watchdog._update_state(n8n_healthy=True, heal_count=5)
        state = watchdog.get_state()
        assert state["n8n_healthy"] is True
        assert state["heal_count"] == 5
        # Reset
        watchdog._update_state(n8n_healthy=False, heal_count=0)


# ── start_watchdog ───────────────────────────────────────────────────────────

class TestStartWatchdog:
    @patch("watchdog.run_watchdog_loop")
    def test_starts_daemon_thread(self, mock_loop):
        t = watchdog.start_watchdog()
        assert t.daemon is True
        assert t.name == "ronkbot-watchdog"
        # Thread may already be stopped since the mock returns immediately,
        # but it was started — verify the mock was called
        t.join(timeout=1)
        mock_loop.assert_called_once()
