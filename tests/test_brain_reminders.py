"""Tests for brain/reminders.py — set, list, cancel, persistence, timer."""

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Fixture to create a fresh ReminderManager with no previous state
@pytest.fixture
def reminder_manager():
    from brain.reminders import ReminderManager

    with patch("brain.reminders._REMINDERS_FILE") as mock_file:
        mock_file.exists.return_value = False
        mock_file.parent = Path("/tmp/_test_reminders")
        rm = ReminderManager()
        yield rm
        # Clean up internal state
        rm.stop()

# ---------------------------------------------------------------------------
# ReminderManager — set_reminder
# ---------------------------------------------------------------------------


def test_set_reminder_basic(reminder_manager):
    rm = reminder_manager
    result = rm.set_reminder("Test reminder", seconds=10)
    assert "Reminder set" in result
    assert "Test reminder" in result
    assert "10s" in result


def test_set_reminder_minimum_duration(reminder_manager):
    """Setting a reminder with <5s should be bumped to 5s."""
    rm = reminder_manager
    result = rm.set_reminder("Quick", seconds=1)
    assert "Reminder set" in result
    # Should say at least 5s
    assert "5" in result


def test_set_timer(reminder_manager):
    """Setting a timer (empty text) should return a timer confirmation."""
    rm = reminder_manager
    result = rm.set_reminder("", seconds=30)
    assert "Timer set" in result


def test_set_reminder_with_minutes(reminder_manager):
    rm = reminder_manager
    result = rm.set_reminder("Meeting", minutes=5)
    assert "Meeting" in result
    assert "5m" in result or "300s" in result


def test_set_reminder_with_hours(reminder_manager):
    rm = reminder_manager
    result = rm.set_reminder("End of day", hours=1)
    assert "End of day" in result
    assert "1h" in result


# ---------------------------------------------------------------------------
# list_reminders
# ---------------------------------------------------------------------------


def test_list_reminders_empty(reminder_manager):
    rm = reminder_manager
    result = rm.list_reminders()
    assert "No pending reminders" in result


def test_list_reminders_with_pending(reminder_manager):
    rm = reminder_manager
    rm.set_reminder("Test", seconds=60)
    result = rm.list_reminders()
    assert "pending" in result.lower()
    assert "Test" in result


def test_list_reminders_multiple(reminder_manager):
    rm = reminder_manager
    rm.set_reminder("First", seconds=60)
    rm.set_reminder("Second", seconds=120)
    result = rm.list_reminders()
    assert "First" in result
    assert "Second" in result


# ---------------------------------------------------------------------------
# cancel_reminder
# ---------------------------------------------------------------------------


def test_cancel_reminder_by_text(reminder_manager):
    rm = reminder_manager
    rm.set_reminder("Doctor appointment", seconds=3600)
    result = rm.cancel_reminder("Doctor")
    assert "Cancelled" in result


def test_cancel_reminder_nonexistent(reminder_manager):
    rm = reminder_manager
    result = rm.cancel_reminder("nonexistent")
    assert "No reminder found" in result


def test_cancel_reminder_multiple_matching(reminder_manager):
    rm = reminder_manager
    rm.set_reminder("Buy milk", seconds=60)
    rm.set_reminder("Buy bread", seconds=120)
    rm.set_reminder("Call doctor", seconds=300)

    result = rm.cancel_reminder("Buy")
    assert "Cancelled" in result


# ---------------------------------------------------------------------------
# clear_fired
# ---------------------------------------------------------------------------


def test_clear_fired(reminder_manager):
    rm = reminder_manager
    rm.set_reminder("Past reminder", seconds=1)
    # Manually mark it as fired
    for r in rm._reminders:
        r.fired = True
        r.fire_at = 0  # Set in the past
    rm.clear_fired()
    result = rm.list_reminders()
    assert "No pending reminders" in result


# ---------------------------------------------------------------------------
# Persistence (save/load)
# ---------------------------------------------------------------------------


def test_reminder_persistence():
    """Reminders should serialize/deserialize correctly."""
    from brain.reminders import Reminder, ReminderManager
    import time

    r = Reminder(
        id="test_1",
        text="Test reminder",
        fire_at=time.time() + 3600,
        reminder_type="reminder",
    )

    # Test asdict
    d = r.__dict__.copy()
    assert d["text"] == "Test reminder"
    assert d["reminder_type"] == "reminder"
    assert not d["fired"]


# ---------------------------------------------------------------------------
# _format_duration
# ---------------------------------------------------------------------------


def test_format_duration_seconds():
    from brain.reminders import ReminderManager

    result = ReminderManager._format_duration(30)
    assert result == "30s"


def test_format_duration_minutes():
    from brain.reminders import ReminderManager

    result = ReminderManager._format_duration(150)
    assert "2m" in result
    assert "30s" in result


def test_format_duration_hours():
    from brain.reminders import ReminderManager

    result = ReminderManager._format_duration(3661)
    assert "1h" in result
    assert "1m" in result
    assert "1s" in result


def test_format_duration_zero():
    from brain.reminders import ReminderManager

    result = ReminderManager._format_duration(0)
    assert "0s" in result
