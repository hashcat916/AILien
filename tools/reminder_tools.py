"""Reminder and timer tools — delegate to the ReminderManager in brain/reminders.py.

Provides the LLM with explicit tools to set, list, and cancel reminders/timers
while the actual scheduling engine lives in brain/reminders.py.
"""

from tools import tool

# The ReminderManager is accessed through a global reference set by main.py
# at startup. This avoids circular imports while keeping the dependency explicit.
_manager = None


def set_manager(manager) -> None:
    """Set the global ReminderManager reference (called by main.py during init)."""
    global _manager
    _manager = manager


def get_manager():
    """Get the current ReminderManager instance."""
    return _manager


@tool(
    name="set_reminder",
    description="Set a reminder that fires after a duration. Use for 'remind me in X minutes to Y'.",
    params={
        "text": {"type": "string", "description": "The reminder message, e.g. 'check the oven', 'call John'"},
        "minutes": {"type": "integer", "description": "Minutes until the reminder fires", "default": 0},
        "hours": {"type": "integer", "description": "Hours until the reminder fires", "default": 0},
        "seconds": {"type": "integer", "description": "Seconds until the reminder fires", "default": 0},
    },
    required=["text"],
)
def set_reminder(text: str, minutes: int = 0, hours: int = 0, seconds: int = 0) -> str:
    if not text.strip():
        return "Please provide a reminder message."
    mgr = get_manager()
    if mgr is None:
        return "Reminder system is not available."
    return mgr.set_reminder(text, minutes=minutes, hours=hours, seconds=seconds)


@tool(
    name="set_timer",
    description="Set a countdown timer. Fires an alert when time's up.",
    params={
        "seconds": {"type": "integer", "description": "Number of seconds for the timer (e.g. 120 for 2 minutes)"},
        "label": {"type": "string", "description": "Optional label for the timer, e.g. 'pasta', 'laundry'", "default": ""},
    },
    required=["seconds"],
)
def set_timer(seconds: int, label: str = "") -> str:
    if seconds < 1:
        return "Timer must be at least 1 second."
    mgr = get_manager()
    if mgr is None:
        return "Timer system is not available."
    return mgr.set_reminder(label or "", seconds=seconds)


@tool(
    name="list_reminders",
    description="List all pending reminders and timers.",
    params={},
    required=[],
)
def list_reminders() -> str:
    mgr = get_manager()
    if mgr is None:
        return "Reminder system is not available."
    return mgr.list_reminders()


@tool(
    name="cancel_reminder",
    description="Cancel a reminder or timer by its text or ID.",
    params={
        "identifier": {"type": "string", "description": "Text to match against reminder messages, or the reminder ID"},
    },
    required=["identifier"],
)
def cancel_reminder(identifier: str) -> str:
    if not identifier.strip():
        return "Please provide a reminder ID or text to cancel."
    mgr = get_manager()
    if mgr is None:
        return "Reminder system is not available."
    return mgr.cancel_reminder(identifier)
