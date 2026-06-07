"""Proactive monitor — watches system health and speaks up proactively.

Runs in a background thread and fires alerts via a callback when it detects
notable events like low battery, high CPU/memory, or completed downloads.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import psutil

logger = logging.getLogger("agent")


@dataclass
class _AlertState:
    """Tracks when an alert type was last fired so we can enforce cooldowns."""

    last_fired: float = 0.0
    last_value: float = 0.0

    def is_on_cooldown(self, cooldown: float = 60.0) -> bool:
        """Check if the alert is still within its cooldown period."""
        return (time.time() - self.last_fired) < cooldown


class ProactiveMonitor:
    """Monitors system health and fires alerts via callback."""

    def __init__(self, alert_callback: Callable[[str], None] | None = None) -> None:
        self._callback = alert_callback
        self._running = False
        self._thread: threading.Thread | None = None
        self._battery_alert = _AlertState()
        self._cpu_alert = _AlertState()
        self._memory_alert = _AlertState()
        self._disk_alert = _AlertState()

    def start(self) -> None:
        """Start the monitoring loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Proactive monitor started")

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _alert(self, message: str) -> None:
        """Fire an alert through the callback."""
        logger.info("Proactive alert: %s", message)
        if self._callback:
            self._callback(message)

    def _monitor_loop(self) -> None:
        """Main monitoring loop — checks every 30 seconds."""
        while self._running:
            try:
                self._check_battery()
                self._check_cpu()
                self._check_memory()
                self._check_disk()
            except Exception as exc:
                logger.debug("Proactive monitor check failed: %s", exc)
            time.sleep(30)

    def _check_battery(self) -> None:
        """Alert on low battery."""
        try:
            for path in Path("/sys/class/power_supply").glob("*/capacity"):
                level = int(path.read_text().strip())
                break
            else:
                return
        except Exception:
            return

        if level < 10 and not self._battery_alert.is_on_cooldown(300):
            self._battery_alert.last_fired = time.time()
            self._battery_alert.last_value = level
            self._alert(f"Warning! Battery is critically low at {level}%. Plug in now.")
        elif level < 20 and not self._battery_alert.is_on_cooldown(120):
            self._battery_alert.last_fired = time.time()
            self._battery_alert.last_value = level
            self._alert(f"Battery is getting low: {level}%. You might want to find a charger soon.")

    def _check_cpu(self) -> None:
        """Alert on sustained high CPU."""
        cpu = psutil.cpu_percent(interval=1)
        if cpu > 90 and not self._cpu_alert.is_on_cooldown(120):
            self._cpu_alert.last_fired = time.time()
            self._cpu_alert.last_value = cpu
            self._alert(f"CPU usage is very high: {cpu}%. Something may be overloading the system.")

    def _check_memory(self) -> None:
        """Alert on high memory usage."""
        mem = psutil.virtual_memory()
        if mem.percent > 90 and not self._memory_alert.is_on_cooldown(120):
            self._memory_alert.last_fired = time.time()
            self._memory_alert.last_value = mem.percent
            self._alert(
                f"Memory usage is high: {mem.percent}% "
                f"({mem.used // (1024**3)}GB of {mem.total // (1024**3)}GB)."
            )

    def _check_disk(self) -> None:
        """Alert on low disk space."""
        try:
            usage = psutil.disk_usage("/")
            percent = usage.percent
            free_gb = usage.free // (1024**3)
            if percent > 95 and not self._disk_alert.is_on_cooldown(600):
                self._disk_alert.last_fired = time.time()
                self._disk_alert.last_value = percent
                self._alert(f"Disk space critically low: {percent}% used. Only {free_gb}GB free.")
            elif percent > 90 and not self._disk_alert.is_on_cooldown(3600):
                self._disk_alert.last_fired = time.time()
                self._disk_alert.last_value = percent
                self._alert(f"Disk is getting full: {percent}% used. Only {free_gb}GB remaining.")
        except Exception:
            pass
