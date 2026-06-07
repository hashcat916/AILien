"""System tray icon for AILIEN — left-click opens control panel, right-click shows menu.

Uses pystray with appindicator backend (auto-detected) for the system tray.
Left-click opens a tkinter-based control panel with toggles and actions.
Right-click shows a context menu with the same options.

The icon color changes to reflect agent status (idle, listening, thinking, speaking).
"""

import logging
import os
import subprocess
import threading
from pathlib import Path

import config
from utils.helpers import notify

logger = logging.getLogger("agent")

# Let pystray auto-detect the best backend for the desktop environment.
# Do NOT force "xorg" — XFCE needs the appindicator backend which is detected
# automatically when PYSTRAY_BACKEND is not set.
os.environ.pop("PYSTRAY_BACKEND", None)


def _create_emoji_icon(size: int = 64, accent_color: tuple | None = None) -> "Image.Image":
    """Create a tray icon using the alien PNG on a colored circular background.

    Args:
        size: Icon size in pixels.
        accent_color: Background circle color (R, G, B, A). Default is gray.
    """
    from PIL import Image, ImageDraw

    color = accent_color or (128, 128, 128, 255)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw background circle
    margin = max(1, size // 32)
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color,
        outline=_darken_color(color, 0.7),
        width=max(1, size // 48),
    )

    # Load the alien icon and composite it onto the circle
    try:
        # First check the tracked icons/ directory, fall back to .cache/
        icon_path = config.PROJECT_DIR / "icons" / "ailien_icon.png"
        if not icon_path.exists():
            icon_path = config.CACHE_DIR / "ailien_icon.png"
        if icon_path.exists():
            alien = Image.open(str(icon_path)).convert("RGBA")
            # Scale to fit inside the circle
            circle_size = size - margin * 2
            alien = alien.resize((circle_size, circle_size), Image.LANCZOS)
            # Center it
            offset = (size - circle_size) // 2
            img.paste(alien, (offset, offset), alien)
    except Exception:
        pass

    return img


def _darken_color(rgba: tuple, factor: float = 0.6) -> tuple:
    r, g, b, a = rgba
    return (int(r * factor), int(g * factor), int(b * factor), a)


STATUS_LABELS = {
    "idle": "Idle",
    "listening": "Listening...",
    "thinking": "Thinking...",
    "speaking": "Speaking...",
    "closed": "Stopped",
}

STATUS_COLORS = {
    "idle": (128, 128, 128, 255),       # gray
    "listening": (74, 222, 128, 255),   # green
    "thinking": (251, 191, 36, 255),    # yellow
    "speaking": (96, 165, 250, 255),    # blue
    "closed": (128, 128, 128, 255),     # gray
}


class TrayIcon:
    """System tray icon with left-click control panel and right-click menu."""

    def __init__(self, overlay=None) -> None:
        self.overlay = overlay
        self._icon = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._status = "idle"
        self._status_lock = threading.Lock()
        self._control_panel = None
        self._agent_ref = None  # Reference to the Agent for mode switching

        # Lazy-import control panel to avoid circular imports at module level
        self._init_control_panel()

    def _init_control_panel(self) -> None:
        """Create the control panel (lazy, in background thread)."""
        try:
            from gui.control_panel import ControlPanel
            self._control_panel = ControlPanel()
            logger.info("Control panel created")
        except Exception as exc:
            logger.debug("Control panel unavailable: %s", exc)

    def set_agent(self, agent) -> None:
        """Store a reference to the agent for menu actions."""
        self._agent_ref = agent

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------

    @staticmethod
    def _toggle_voice(icon, item) -> None:
        config.AGENT_VOICE_FEEDBACK = not config.AGENT_VOICE_FEEDBACK
        logger.info("Voice feedback set to %s", config.AGENT_VOICE_FEEDBACK)
        if icon is not None:
            try:
                icon.update_menu()
            except Exception:
                pass

    @staticmethod
    def _toggle_proactive(icon, item) -> None:
        config.JARVIS_PROACTIVE = not config.JARVIS_PROACTIVE
        logger.info("Proactive alerts set to %s", config.JARVIS_PROACTIVE)
        if icon is not None:
            try:
                icon.update_menu()
            except Exception:
                pass

    @staticmethod
    def _toggle_confirm_dangerous(icon, item) -> None:
        config.AGENT_CONFIRM_DANGEROUS = not config.AGENT_CONFIRM_DANGEROUS
        logger.info("Confirm dangerous actions set to %s", config.AGENT_CONFIRM_DANGEROUS)
        if icon is not None:
            try:
                icon.update_menu()
            except Exception:
                pass

    @staticmethod
    def _open_log_file(icon, item) -> None:
        try:
            log_path = config.LOG_FILE.resolve()
            subprocess.Popen(
                ["xdg-open", str(log_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.warning("Could not open log file: %s", exc)

    @staticmethod
    def _open_knowledge(icon, item) -> None:
        """Open the knowledge folder in the file manager."""
        try:
            knowledge_dir = config.PROJECT_DIR / "knowledge"
            knowledge_dir.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(
                ["xdg-open", str(knowledge_dir)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.warning("Could not open knowledge folder: %s", exc)

    def _open_terminal(self, icon, item) -> None:
        """Open a terminal with AILIEN in text mode."""
        try:
            terminal_cmd = os.environ.get(
                "TERMINAL",
                os.environ.get("TERM", "x-terminal-emulator"),
            )
            subprocess.Popen(
                [terminal_cmd, "-e",
                 f"bash -c 'cd {config.PROJECT_DIR} && .venv/bin/python3 main.py --text; exec bash'"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.warning("Could not open terminal: %s", exc)

    def _about(self, icon, item) -> None:
        """Show a simple about dialog."""
        from tkinter import messagebox
        try:
            messagebox.showinfo(
                "About AILIEN",
                "AILIEN 👽\n\n"
                "AI computer control assistant\n\n"
                "Version: 1.0\n"
                "Python + pystray + tkinter",
            )
        except Exception:
            pass

    def _quit_agent(self, icon, item) -> None:
        logger.info("Quit requested from tray menu")
        notify("AILIEN", "Agent stopped")
        self._stop_event.set()
        if self.overlay is not None:
            try:
                self.overlay.close()
            except Exception:
                pass
        if self._control_panel is not None:
            try:
                self._control_panel.close()
            except Exception:
                pass
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass

    def _open_control_panel(self, icon, item) -> None:
        """Open the control panel from the menu."""
        self._show_control_panel()

    def _show_control_panel(self) -> None:
        """Show (or toggle) the control panel window."""
        if self._control_panel is not None:
            self._control_panel.toggle()

    # ------------------------------------------------------------------
    # Menu building
    # ------------------------------------------------------------------

    def _build_menu(self):
        """Build the right-click context menu."""
        import pystray

        return pystray.Menu(
            # Header
            pystray.MenuItem(
                "[A] AILIEN",
                self._open_control_panel,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            # Status readout
            pystray.MenuItem(
                lambda: f"Status: {STATUS_LABELS.get(self._status, self._status)}",
                lambda icon, item: None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            # Toggles
            pystray.MenuItem(
                "Voice Feedback",
                self._toggle_voice,
                checked=lambda item: config.AGENT_VOICE_FEEDBACK,
            ),
            pystray.MenuItem(
                "Proactive Alerts",
                self._toggle_proactive,
                checked=lambda item: config.JARVIS_PROACTIVE,
            ),
            pystray.MenuItem(
                "Confirm Dangerous",
                self._toggle_confirm_dangerous,
                checked=lambda item: config.AGENT_CONFIRM_DANGEROUS,
            ),
            pystray.Menu.SEPARATOR,
            # Control Panel toggle
            pystray.MenuItem(
                "Open Control Panel",
                self._open_control_panel,
            ),
            pystray.Menu.SEPARATOR,
            # Actions
            pystray.MenuItem(
                "Open Terminal Chat",
                self._open_terminal,
            ),
            pystray.MenuItem(
                "Open Knowledge Folder",
                self._open_knowledge,
            ),
            pystray.MenuItem(
                "Open Log File",
                self._open_log_file,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "About AILIEN",
                self._about,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Quit",
                self._quit_agent,
            ),
        )

    # ------------------------------------------------------------------
    # Icon management
    # ------------------------------------------------------------------

    def put_status(self, status: str) -> None:
        """Update the tray icon color and tooltip."""
        with self._status_lock:
            self._status = status
        self._update_icon_color(status)
        if self._icon is not None:
            try:
                label = STATUS_LABELS.get(status, status.capitalize())
                self._icon.title = f"AILIEN - {label}"
            except Exception:
                pass
        # Also update control panel if it exists
        if self._control_panel is not None:
            try:
                self._control_panel.put_status(status)
            except Exception:
                pass

    def _update_icon_color(self, status: str) -> None:
        """Recreate the icon with a color matching the current status."""
        color = STATUS_COLORS.get(status, STATUS_COLORS["idle"])
        try:
            new_image = _create_emoji_icon(64, accent_color=color)
            if self._icon is not None:
                self._icon.icon = new_image
        except Exception:
            pass

    def _run_icon(self) -> None:
        """Run the pystray icon in a background thread.

        On XFCE with the appindicator backend, this creates a GTK status
        icon that appears in the notification area. The menu appears on
        right-click by default in most environments.
        """
        try:
            import pystray
        except Exception as exc:
            logger.warning("pystray unavailable: %s", exc)
            return

        try:
            image = _create_emoji_icon(64)
            menu = self._build_menu()

            # Create the icon with a default action (left-click on most DEs)
            self._icon = pystray.Icon(
                "ailien",
                image,
                "AILIEN — AI Computer Control",
                menu=menu,
            )

            self._icon.run()
        except Exception as exc:
            logger.warning("Tray icon failed to start: %s", exc)

    def start(self) -> None:
        """Start the tray icon in a background thread."""
        self._thread = threading.Thread(target=self._run_icon, daemon=True)
        self._thread.start()
        logger.info("Tray icon started")

    def stop(self) -> None:
        """Stop the tray icon."""
        self._stop_event.set()
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)
