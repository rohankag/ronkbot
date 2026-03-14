"""
tests/test_brain_todos.py — Phase 2 tests for todo CRUD + alert suppression

Run from project root:
    cd scripts/mac-agent && python3 -m pytest ../../tests/test_brain_todos.py -v
"""
import sys, os, pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Point brain at a temporary test DB
os.environ["RONKBOT_TEST"] = "1"

# Patch the brain dir to a temp location
import tempfile
_tmp = tempfile.mkdtemp()
import brain as Brain
Brain.BRAIN_DB = Path(_tmp) / "test_brain.db"
Brain.BRAIN_DIR = Path(_tmp)
Brain.MEMORY_MD = Path(_tmp) / "MEMORY.md"
Brain.DAILY_DIR = Path(_tmp) / "daily"
Brain.DAILY_DIR.mkdir(parents=True, exist_ok=True)
Brain.SOUL_FILE = Path(_tmp) / "soul.yaml"
# Reinitialise so new tables are created in the temp DB
Brain._thread_local = Brain.threading.local()
Brain.init_db()

CHAT = "test_chat_001"


# ── Todo CRUD ──────────────────────────────────────────────────────────────────

def _ts_offset(minutes: int) -> str:
    """Return ISO8601 UTC timestamp offset by `minutes` from now."""
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def test_create_todo_basic():
    t = Brain.create_todo(CHAT, "Buy milk")
    assert t["id"] > 0
    assert t["task"] == "Buy milk"
    assert t["due_at"] is None


def test_create_todo_with_times():
    due = _ts_offset(60)
    remind = _ts_offset(50)
    t = Brain.create_todo(CHAT, "Call dentist", due_at=due, remind_at=remind)
    assert t["due_at"] == due
    assert t["remind_at"] == remind


def test_get_todos_excludes_completed():
    Brain.create_todo(CHAT, "Active task")
    # Create a completed one
    t = Brain.create_todo(CHAT, "Done task")
    Brain.update_todo(t["id"], completed=True)

    active = Brain.get_todos(CHAT, completed=False)
    tasks = [x["task"] for x in active]
    assert "Done task" not in tasks
    assert "Active task" in tasks


def test_due_soon_filter():
    """Tasks with remind_at in next 15 minutes should appear in due_soon=15."""
    remind_soon = _ts_offset(10)      # 10 min from now → should appear
    remind_later = _ts_offset(30)     # 30 min from now → should NOT appear

    t_soon = Brain.create_todo(CHAT, "Soon task", remind_at=remind_soon)
    t_later = Brain.create_todo(CHAT, "Later task", remind_at=remind_later)

    due_soon = Brain.get_todos(CHAT, due_soon_minutes=15)
    ids = [x["id"] for x in due_soon]
    assert t_soon["id"] in ids
    assert t_later["id"] not in ids


def test_due_soon_excludes_already_sent():
    """Tasks where reminder_sent=1 should NOT appear in due_soon."""
    remind = _ts_offset(5)
    t = Brain.create_todo(CHAT, "Already reminded", remind_at=remind)
    Brain.update_todo(t["id"], reminder_sent=True)

    due_soon = Brain.get_todos(CHAT, due_soon_minutes=15)
    ids = [x["id"] for x in due_soon]
    assert t["id"] not in ids


def test_update_todo_mark_complete():
    t = Brain.create_todo(CHAT, "Complete me")
    result = Brain.update_todo(t["id"], completed=True)
    assert result["ok"] is True
    completed = Brain.get_todos(CHAT, completed=True)
    ids = [x["id"] for x in completed]
    assert t["id"] in ids


# ── Recurring todos ───────────────────────────────────────────────────────────

def test_recurrence_daily_creates_next():
    due = "2026-03-10T09:00:00+00:00"
    t = Brain.create_todo(CHAT, "Daily standup", due_at=due, recurrence="daily")
    result = Brain.update_todo(t["id"], completed=True)
    assert result["ok"] is True
    nxt = result["next_todo"]
    assert nxt is not None
    assert nxt["task"] == "Daily standup"
    assert nxt["due_at"] == "2026-03-11T09:00:00+00:00"
    assert nxt["recurrence"] == "daily"


def test_recurrence_weekly():
    due = "2026-03-10T09:00:00+00:00"
    t = Brain.create_todo(CHAT, "Weekly review", due_at=due, recurrence="weekly")
    result = Brain.update_todo(t["id"], completed=True)
    nxt = result["next_todo"]
    assert nxt["due_at"] == "2026-03-17T09:00:00+00:00"


def test_recurrence_monthly_jan31_feb28():
    due = "2026-01-31T12:00:00+00:00"
    t = Brain.create_todo(CHAT, "Monthly report", due_at=due, recurrence="monthly")
    result = Brain.update_todo(t["id"], completed=True)
    nxt = result["next_todo"]
    assert nxt["due_at"] == "2026-02-28T12:00:00+00:00"


def test_recurrence_monthly_dec_to_jan():
    due = "2026-12-15T10:00:00+00:00"
    t = Brain.create_todo(CHAT, "Month-end check", due_at=due, recurrence="monthly")
    result = Brain.update_todo(t["id"], completed=True)
    nxt = result["next_todo"]
    assert nxt["due_at"] == "2027-01-15T10:00:00+00:00"


def test_recurrence_monthly_leap_year():
    due = "2028-01-31T08:00:00+00:00"
    t = Brain.create_todo(CHAT, "Leap check", due_at=due, recurrence="monthly")
    result = Brain.update_todo(t["id"], completed=True)
    nxt = result["next_todo"]
    assert nxt["due_at"] == "2028-02-29T08:00:00+00:00"


def test_recurrence_null_dates():
    """Recurring todo with no due_at/remind_at still creates next instance."""
    t = Brain.create_todo(CHAT, "No dates", recurrence="daily")
    result = Brain.update_todo(t["id"], completed=True)
    nxt = result["next_todo"]
    assert nxt is not None
    assert nxt["task"] == "No dates"
    assert nxt["due_at"] is None
    assert nxt["remind_at"] is None
    assert nxt["recurrence"] == "daily"


def test_no_recurrence_no_next():
    """Non-recurring todo should not create a next instance."""
    t = Brain.create_todo(CHAT, "One-off task")
    result = Brain.update_todo(t["id"], completed=True)
    assert result["ok"] is True
    assert result["next_todo"] is None


def test_recurrence_preserves_remind_offset():
    """Both due_at and remind_at advance by the same recurrence period."""
    due = "2026-03-10T09:00:00+00:00"
    remind = "2026-03-10T08:00:00+00:00"
    t = Brain.create_todo(CHAT, "Offset test", due_at=due, remind_at=remind, recurrence="weekly")
    result = Brain.update_todo(t["id"], completed=True)
    nxt = result["next_todo"]
    assert nxt["due_at"] == "2026-03-17T09:00:00+00:00"
    assert nxt["remind_at"] == "2026-03-17T08:00:00+00:00"


def test_update_returns_dict():
    """update_todo now returns a dict, not a bool."""
    t = Brain.create_todo(CHAT, "Dict check")
    result = Brain.update_todo(t["id"], task="Updated text")
    assert isinstance(result, dict)
    assert result["ok"] is True


def test_create_returns_recurrence():
    """create_todo return dict includes the recurrence field."""
    t = Brain.create_todo(CHAT, "Recurring", recurrence="weekly")
    assert "recurrence" in t
    assert t["recurrence"] == "weekly"


def test_recurrence_update_allowed():
    """Can update the recurrence field on an existing todo."""
    t = Brain.create_todo(CHAT, "Change recurrence")
    result = Brain.update_todo(t["id"], recurrence="monthly")
    assert result["ok"] is True
    # Verify in DB
    todos = Brain.get_todos(CHAT, completed=False)
    match = [x for x in todos if x["id"] == t["id"]]
    assert match[0]["recurrence"] == "monthly"


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_todo():
    """Deleting an existing todo returns True."""
    t = Brain.create_todo(CHAT, "Delete me")
    assert Brain.delete_todo(t["id"]) is True


def test_delete_nonexistent_todo():
    """Deleting a missing ID returns False."""
    assert Brain.delete_todo(999999) is False


def test_delete_removes_from_list():
    """Deleted todo doesn't appear in get_todos."""
    t = Brain.create_todo(CHAT, "Vanish task")
    Brain.delete_todo(t["id"])
    todos = Brain.get_todos(CHAT, completed=False)
    ids = [x["id"] for x in todos]
    assert t["id"] not in ids


# ── Alert suppression ──────────────────────────────────────────────────────────

def test_alert_first_time_should_fire():
    """An alert that has never been sent should always return should_alert=True."""
    result = Brain.should_alert("disk_full_test_1")
    assert result is True


def test_alert_ack_prevents_immediate_repeat():
    """After ack, should_alert returns False within the suppression window."""
    Brain.ack_alert("disk_full_test_2")
    result = Brain.should_alert("disk_full_test_2")
    assert result is False


def test_alert_suppression_different_types_independent():
    """Acking one alert type doesn't suppress a different type."""
    Brain.ack_alert("disk_full_test_3")
    # A different type should still fire
    result = Brain.should_alert("high_memory_test_3")
    assert result is True


def test_alert_ack_idempotent():
    """Multiple acks should not crash and should keep suppressing."""
    Brain.ack_alert("disk_full_test_4")
    Brain.ack_alert("disk_full_test_4")  # second ack
    result = Brain.should_alert("disk_full_test_4")
    assert result is False
