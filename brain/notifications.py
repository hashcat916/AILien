"""Notification mirror — listens for desktop notifications and speaks them aloud.

Uses D-Bus (org.freedesktop.Notifications) to monitor system notifications.
When a notification is received, it's spoken via the TTS callback.

Works on any Linux desktop with a notification daemon (GNOME, KDE, XFCE, etc.).
"""

import logging
import threading
from typing import Callable

logger = logging.getLogger("agent")


class NotificationMirror:
    """Listens for desktop notifications and echoes them via TTS."""

    def __init__(self, speak_callback: Callable[[str], None] | None = None) -> None:
        self._callback = speak_callback
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_ids: set[int] = set()
        self._filtered_apps: set[str] = {
            "AILIEN",  # Don't echo our own notifications
        }

    def start(self) -> None:
        """Start the notification listener in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Notification mirror started")

    def stop(self) -> None:
        """Stop listening."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _listen_loop(self) -> None:
        """Listen for notifications via D-Bus monitoring."""
        try:
            import dbus
            import dbus.mainloop.glib
            from gi.repository import GLib
        except ImportError:
            logger.warning(
                "Notification mirror requires PyGObject and dbus-python. "
                "Install: pip install dbus-python PyGObject"
            )
            return

        # Only try once — if it fails, don't retry
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        try:
            bus = dbus.SessionBus()
            obj = bus.get_object(
                "org.freedesktop.Notifications",
                "/org/freedesktop/Notifications",
            )
            interface = dbus.Interface(obj, "org.freedesktop.Notifications")
        except Exception as exc:
            logger.warning("Could not connect to notifications D-Bus: %s", exc)
            return

        def _on_notification(bus_id: int, app_name: str, replaces_id: int,
                             app_icon: str, summary: str, body: str,
                             actions: list, hints: dict, timeout: int) -> None:
            """Callback for incoming notifications."""
            if app_name in self._filtered_apps:
                return
            # Deduplicate
            if bus_id in self._last_ids:
                return
            self._last_ids.add(bus_id)
            if len(self._last_ids) > 100:
                self._last_ids.clear()

            if summary or body:
                message = f"{summary}" if not body else f"{summary}. {body}"
                logger.info("Notification: %s", message)
                if self._callback:
                    self._callback(message)

        # Register the notification signal handler
        interface.connect_to_signal("Notify", _on_notification)

        # Run the GLib main loop
        loop = GLib.MainLoop()
        try:
            loop.run()
        except Exception:
            pass

    def speak(self, message: str) -> None:
        """Directly speak a message through the callback."""
        if self._callback:
            self._callback(message)


