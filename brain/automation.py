"""Automation engine — schedule tasks to run at intervals or specific times.

Each automation stores:
- A schedule (every N seconds/minutes/hours, or at specific time daily)
- An action (tool name + params to call)
- An enabled/disabled state

The engine runs a background thread that checks every 15 seconds and fires
due automations by calling the stored tool.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, time as dtime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import config

logger = logging.getLogger("agent")

_AUTOMATIONS_FILE = config.CACHE_DIR / "automations.json"


class ScheduleType(Enum):
    INTERVAL = "interval"       # Every N seconds/minutes/hours
    DAILY = "daily"             # At a specific time each day
    HOURLY = "hourly"           # At a specific minute each hour


@dataclass
class Automation:
    """A single scheduled automation."""

    id: str
    label: str
    schedule_type: ScheduleType
    interval_seconds: int = 0          # For INTERVAL
    daily_hour: int = 0                # For DAILY
    daily_minute: int = 0              # For DAILY
    hourly_minute: int = 0             # For HOURLY
    tool_name: str = ""                # Tool to call when triggered
    tool_params: dict[str, Any] = field(default_factory=dict)  # Params for the tool
    enabled: bool = True
    last_fired_at: float = 0.0         # Unix timestamp of last fire
    created_at: float = field(default_factory=time.time)

    @property
    def is_due(self) -> bool:
        """Check if this automation should fire now."""
        if not self.enabled:
            return False

        now = time.time()
        if self.schedule_type == ScheduleType.INTERVAL:
            return (now - self.last_fired_at) >= self.interval_seconds

        elif self.schedule_type == ScheduleType.DAILY:
            # Check if the daily time has passed and we haven't fired today
            current = datetime.now()
            target = current.replace(hour=self.daily_hour, minute=self.daily_minute, second=0, microsecond=0)
            if current >= target:
                # Haven't fired since the target time today
                last_fired_dt = datetime.fromtimestamp(self.last_fired_at)
                return last_fired_dt.date() < current.date() and current >= target
            return False

        elif self.schedule_type == ScheduleType.HOURLY:
            current = datetime.now()
            if current.minute >= self.hourly_minute:
                last_fired_dt = datetime.fromtimestamp(self.last_fired_at)
                if last_fired_dt.hour < current.hour or last_fired_dt.date() < current.date():
                    return True
            return False

        return False


class AutomationEngine:
    """Background engine that checks and fires scheduled automations."""

    def __init__(self, tool_executor: Callable[[str, dict], str] | None = None):
        self._automations: list[Automation] = []
        self._lock = threading.Lock()
        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._tool_executor = tool_executor  # Function to call: (tool_name, params) -> str
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_automation(
        self,
        label: str,
        schedule_type: str,
        tool_name: str,
        tool_params: dict[str, Any] | None = None,
        interval_seconds: int = 0,
        daily_hour: int = 0,
        daily_minute: int = 0,
        hourly_minute: int = 0,
    ) -> str:
        """Add a new automation.

        *schedule_type*: 'interval', 'daily', or 'hourly'
        Returns a confirmation string.
        """
        try:
            st = ScheduleType(schedule_type)
        except ValueError:
            return f"Invalid schedule type '{schedule_type}'. Use: interval, daily, or hourly."

        # Validate schedule params
        if st == ScheduleType.INTERVAL and interval_seconds < 30:
            return "Interval must be at least 30 seconds."

        aid = f"auto_{int(time.time())}_{len(self._automations)}"

        auto = Automation(
            id=aid,
            label=label,
            schedule_type=st,
            interval_seconds=interval_seconds,
            daily_hour=daily_hour,
            daily_minute=daily_minute,
            hourly_minute=hourly_minute,
            tool_name=tool_name,
            tool_params=tool_params or {},
        )

        with self._lock:
            self._automations.append(auto)
            self._save()

        schedule_str = self._format_schedule(auto)
        return f"Automation added: '{label}' — {schedule_str} → {tool_name}({tool_params or {}})"

    def list_automations(self) -> str:
        """Return a formatted list of all automations."""
        with self._lock:
            if not self._automations:
                return "No automations set up."

            lines = [f"Automations ({len(self._automations)}):"]
            for a in self._automations:
                status = "✅ ON" if a.enabled else "⏸️ OFF"
                schedule = self._format_schedule(a)
                last_fired = ""
                if a.last_fired_at > 0:
                    last_fired = f" (last: {datetime.fromtimestamp(a.last_fired_at).strftime('%H:%M')})"
                lines.append(
                    f"  {status}  {a.label}\n"
                    f"       Schedule: {schedule}{last_fired}\n"
                    f"       Action: {a.tool_name}({a.tool_params})"
                )
            return "\n".join(lines)

    def remove_automation(self, identifier: str) -> str:
        """Remove an automation by ID or label text match."""
        with self._lock:
            before = len(self._automations)
            remaining = [a for a in self._automations if a.id != identifier]
            if len(remaining) == before:
                # Try label match
                remaining = [
                    a for a in self._automations
                    if identifier.lower() not in a.label.lower()
                ]
            removed = before - len(remaining)
            self._automations = remaining
            if removed:
                self._save()

        if removed:
            return f"Removed {removed} automation(s)."
        return f"No automation found matching '{identifier}'."

    def pause_automation(self, identifier: str) -> str:
        """Pause an automation by ID or label."""
        return self._set_enabled(identifier, False)

    def resume_automation(self, identifier: str) -> str:
        """Resume a paused automation by ID or label."""
        return self._set_enabled(identifier, True)

    def pause_all(self) -> str:
        """Pause all automations at once."""
        with self._lock:
            for a in self._automations:
                if a.enabled:
                    a.enabled = False
            self._save()
        return "All automations paused."

    def resume_all(self) -> str:
        """Resume all automations."""
        with self._lock:
            for a in self._automations:
                a.enabled = True
            self._save()
        return "All automations resumed."

    def _set_enabled(self, identifier: str, enabled: bool) -> str:
        """Set an automation's enabled state."""
        with self._lock:
            found = False
            for a in self._automations:
                if a.id == identifier or identifier.lower() in a.label.lower():
                    a.enabled = enabled
                    found = True
                    break
            if found:
                self._save()

        state = "resumed" if enabled else "paused"
        if found:
            return f"Automation '{identifier}' {state}."
        return f"No automation found matching '{identifier}'."

    # ------------------------------------------------------------------
    # Engine lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background checking thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        enabled = sum(1 for a in self._automations if a.enabled)
        logger.info("Automation engine started (%d automations, %d active)", len(self._automations), enabled)

    def stop(self) -> None:
        """Stop the background thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def set_paused(self, paused: bool) -> None:
        """Pause or resume the entire engine without removing automations."""
        self._paused = paused
        logger.info("Automation engine %s", "paused" if paused else "resumed")

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_loop(self) -> None:
        """Background loop that checks for due automations every 15 seconds."""
        while self._running:
            if not self._paused:
                due: list[Automation] = []
                with self._lock:
                    for a in self._automations:
                        if a.is_due:
                            due.append(a)

                for a in due:
                    self._fire_automation(a)
                    with self._lock:
                        a.last_fired_at = time.time()
                        self._save()

            time.sleep(15)

    def _fire_automation(self, auto: Automation) -> None:
        """Execute an automation's action."""
        logger.info("Automation firing: %s → %s(%s)", auto.label, auto.tool_name, auto.tool_params)
        if self._tool_executor:
            try:
                result = self._tool_executor(auto.tool_name, auto.tool_params)
                logger.info("Automation result: %s", result[:200] if result else "OK")
            except Exception as exc:
                logger.error("Automation %s failed: %s", auto.label, exc)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load automations from disk."""
        try:
            if _AUTOMATIONS_FILE.exists():
                data = json.loads(_AUTOMATIONS_FILE.read_text(encoding="utf-8"))
                for item in data:
                    item["schedule_type"] = ScheduleType(item["schedule_type"])
                    self._automations.append(Automation(**item))
                if self._automations:
                    logger.info("Loaded %d automation(s)", len(self._automations))
        except Exception as exc:
            logger.warning("Failed to load automations: %s", exc)

    def _save(self) -> None:
        """Save automations to disk."""
        try:
            data = []
            for a in self._automations:
                d = asdict(a)
                d["schedule_type"] = d["schedule_type"].value
                data.append(d)
            _AUTOMATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            _AUTOMATIONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to save automations: %s", exc)

    @staticmethod
    def _format_schedule(auto: Automation) -> str:
        """Human-readable schedule description."""
        if auto.schedule_type == ScheduleType.INTERVAL:
            secs = auto.interval_seconds
            if secs >= 3600:
                return f"every {secs // 3600}h"
            elif secs >= 60:
                return f"every {secs // 60}m"
            return f"every {secs}s"
        elif auto.schedule_type == ScheduleType.DAILY:
            h = auto.daily_hour
            m = auto.daily_minute
            ampm = "AM" if h < 12 else "PM"
            h12 = h % 12 or 12
            return f"daily at {h12}:{m:02d} {ampm}"
        elif auto.schedule_type == ScheduleType.HOURLY:
            return f"hourly at :{auto.hourly_minute:02d}"
        return "unknown"
