"""Reminders and timers for AILIEN.

Provides background-thread-safe functions to:
- Set a reminder for N minutes/hours from now
- Set a countdown timer for N seconds
- List pending reminders
- Cancel a reminder
- Persist reminders across restarts
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import config

logger = logging.getLogger("agent")

_REMINDERS_FILE = config.CACHE_DIR / "reminders.json"


@dataclass
class Reminder:
    """A single reminder or timer."""

    id: str
    text: str
    fire_at: float  # Unix timestamp
    created_at: float = field(default_factory=time.time)
    fired: bool = False
    reminder_type: str = "reminder"  # "reminder" or "timer"

    @property
    def remaining(self) -> timedelta:
        return timedelta(seconds=max(0, self.fire_at - time.time()))

    @property
    def is_due(self) -> bool:
        return not self.fired and time.time() >= self.fire_at


class ReminderManager:
    """Manages reminders in a background thread with persistence."""

    def __init__(self, fire_callback: Callable[[str], None] | None = None):
        self._reminders: list[Reminder] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._fire_callback = fire_callback
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_reminder(self, text: str, minutes: float = 0, hours: float = 0, seconds: float = 0) -> str:
        """Set a reminder that fires after the given duration.

        Returns a human-readable confirmation string.
        """
        total_seconds = seconds + (minutes * 60) + (hours * 3600)
        if total_seconds < 5:
            total_seconds = 5  # Minimum 5 seconds

        fire_at = time.time() + total_seconds
        rid = f"rem_{int(fire_at)}_{len(self._reminders)}"

        is_timer = not bool(text.strip())
        display_text = text.strip() or f"Timer for {self._format_duration(total_seconds)}"

        reminder = Reminder(
            id=rid,
            text=display_text,
            fire_at=fire_at,
            reminder_type="timer" if is_timer else "reminder",
        )

        with self._lock:
            self._reminders.append(reminder)
            self._save()

        duration_str = self._format_duration(total_seconds)
        if is_timer:
            return f"Timer set for {duration_str}."
        return f"Reminder set for {duration_str}: \"{text.strip()}\""

    def list_reminders(self) -> str:
        """Return a formatted list of pending reminders."""
        with self._lock:
            pending = [r for r in self._reminders if not r.fired]

        if not pending:
            return "No pending reminders."

        lines = [f"You have {len(pending)} pending reminder(s):"]
        for r in pending:
            remaining = r.remaining
            timer_label = "[Timer] " if r.reminder_type == "timer" else ""
            lines.append(
                f"  • {timer_label}\"{r.text}\" — due in {self._format_duration(remaining.total_seconds())}"
            )
        return "\n".join(lines)

    def cancel_reminder(self, identifier: str) -> str:
        """Cancel a reminder by ID or text match."""
        with self._lock:
            before = len(self._reminders)
            # Try exact ID match first
            remaining = [r for r in self._reminders if r.fired or (r.id != identifier)]
            if len(remaining) == before:
                # Try text match
                remaining = [
                    r for r in self._reminders
                    if r.fired or identifier.lower() not in r.text.lower()
                ]
            cancelled = before - len(remaining)
            self._reminders = remaining
            if cancelled:
                self._save()

        if cancelled:
            return f"Cancelled {cancelled} reminder(s)."
        return f"No reminder found matching \"{identifier}\"."

    def clear_fired(self) -> None:
        """Remove all fired reminders from the list."""
        with self._lock:
            before = len(self._reminders)
            self._reminders = [r for r in self._reminders if not r.fired]
            if len(self._reminders) < before:
                self._save()

    def start(self) -> None:
        """Start the background checking thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        logger.info("Reminder manager started (%d pending)", len(self._reminders))

    def stop(self) -> None:
        """Stop the background thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_loop(self) -> None:
        """Background loop that checks for due reminders every second."""
        while self._running:
            due: list[Reminder] = []
            with self._lock:
                for r in self._reminders:
                    if r.is_due:
                        r.fired = True
                        due.append(r)
                if due:
                    self._save()

            for r in due:
                label = "⏰ Timer" if r.reminder_type == "timer" else "🔔 Reminder"
                message = f"{label}: {r.text}"
                logger.info("Reminder fired: %s", r.text)
                if self._fire_callback:
                    self._fire_callback(message)

            time.sleep(1.0)

    def _load(self) -> None:
        """Load reminders from disk."""
        try:
            if _REMINDERS_FILE.exists():
                data = json.loads(_REMINDERS_FILE.read_text(encoding="utf-8"))
                for item in data:
                    r = Reminder(**item)
                    if not r.fired and r.fire_at > time.time():
                        self._reminders.append(r)
                if self._reminders:
                    logger.info("Loaded %d pending reminder(s)", len(self._reminders))
        except Exception as exc:
            logger.warning("Failed to load reminders: %s", exc)

    def _save(self) -> None:
        """Save reminders to disk."""
        try:
            data = [asdict(r) for r in self._reminders if not r.fired]
            _REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            _REMINDERS_FILE.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("Failed to save reminders: %s", exc)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds into a human-readable duration string."""
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: ReminderManager | None = None
_lock = threading.Lock()


def get_manager(fire_callback: Callable[[str], None] | None = None) -> ReminderManager:
    """Get or create the global ReminderManager instance."""
    global _manager
    if _manager is None:
        with _lock:
            if _manager is None:
                _manager = ReminderManager(fire_callback=fire_callback)
    return _manager
