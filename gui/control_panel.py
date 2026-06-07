"""Floating control panel for AILIEN — toggles, status, and quick actions.

A compact always-on-top tkinter window that shows the agent's current status
and provides toggle switches for settings, plus quick-action buttons.

Opened by left-clicking the system tray icon.
"""

import logging
import os
import subprocess
import threading
from queue import Empty, Queue
from typing import Any

import config

logger = logging.getLogger("agent")

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    tk = None  # type: ignore

STATUS_COLORS = {
    "idle": "#808080",
    "listening": "#4ade80",
    "thinking": "#fbbf24",
    "speaking": "#60a5fa",
    "closed": "#808080",
}

STATUS_LABELS = {
    "idle": "Idle",
    "listening": "Listening...",
    "thinking": "Thinking...",
    "speaking": "Speaking...",
    "closed": "",
}


class ControlPanel:
    """Floating control panel with status, toggles, and quick actions.

    Runs in its own tkinter thread.  Thread-safe status updates are sent
    via ``put_status()``.  Call ``toggle()`` to show/hide the window.
    """

    def __init__(self) -> None:
        if tk is None:
            raise RuntimeError("tkinter is not available")

        self._queue: Queue[str] = Queue()
        self._status = "idle"
        self._visible = False
        self._root: tk.Tk | None = None

        # Widget references
        self._indicator: tk.Canvas | None = None
        self._indicator_dot: int | None = None
        self._status_label: tk.Label | None = None
        self._voice_var: tk.BooleanVar | None = None
        self._proactive_var: tk.BooleanVar | None = None
        self._confirm_var: tk.BooleanVar | None = None

        self._start_thread()

    # ------------------------------------------------------------------
    # Thread management
    # ------------------------------------------------------------------

    def _start_thread(self) -> None:
        """Build the UI in a background thread."""
        self._thread = threading.Thread(target=self._build_ui, daemon=True)
        self._thread.start()

    def _build_ui(self) -> None:
        """Create the tkinter window (runs in background thread)."""
        self._root = tk.Tk()
        self._root.title("AILIEN Control Panel")
        self._root.configure(bg="#1e1e1e")
        self._root.overrideredirect(False)  # normal window with title bar
        self._root.attributes("-topmost", True)
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Position near top-right of screen
        sw = self._root.winfo_screenwidth()
        self._root.geometry(f"320x380+{sw - 360}+40")

        # ---- widgets ---------------------------------------------------
        self._build_header()
        self._build_status_section()
        self._build_separator()
        self._build_toggles()
        self._build_separator()
        self._build_actions()
        self._build_separator()
        self._build_footer()

        # Start hidden
        self._root.withdraw()

        # ---- poll queue ------------------------------------------------
        self._poll_queue()
        self._root.mainloop()

    # ------------------------------------------------------------------
    # UI sections
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        """Top header with icon and title."""
        frame = tk.Frame(self._root, bg="#1e1e1e")
        frame.pack(fill="x", padx=16, pady=(12, 4))

        # Alien emoji + title
        title = tk.Label(
            frame,
            text="👽  AILIEN",
            font=("Helvetica", 16, "bold"),
            fg="#4ade80",
            bg="#1e1e1e",
        )
        title.pack(side="left")

    def _build_status_section(self) -> None:
        """Status indicator circle + text."""
        frame = tk.Frame(self._root, bg="#1e1e1e")
        frame.pack(fill="x", padx=16, pady=(4, 8))

        # Colored dot
        self._indicator = tk.Canvas(frame, width=20, height=20, bg="#1e1e1e", highlightthickness=0)
        self._indicator.pack(side="left", padx=(0, 8))
        self._indicator_dot = self._indicator.create_oval(
            2, 2, 18, 18, fill=STATUS_COLORS["idle"], outline=""
        )

        # Status text
        self._status_label = tk.Label(
            frame,
            text="Idle",
            font=("Helvetica", 12),
            fg="#cccccc",
            bg="#1e1e1e",
        )
        self._status_label.pack(side="left")

    def _build_separator(self) -> None:
        """Thin horizontal line."""
        sep = tk.Frame(self._root, height=1, bg="#333333")
        sep.pack(fill="x", padx=16, pady=4)

    def _build_toggles(self) -> None:
        """Toggle switches for settings."""
        frame = tk.Frame(self._root, bg="#1e1e1e")
        frame.pack(fill="x", padx=16, pady=4)

        toggles = [
            ("Voice Feedback", "AGENT_VOICE_FEEDBACK"),
            ("Proactive Alerts", "JARVIS_PROACTIVE"),
            ("Confirm Dangerous", "AGENT_CONFIRM_DANGEROUS"),
        ]

        self._voice_var = tk.BooleanVar(value=config.AGENT_VOICE_FEEDBACK)
        self._proactive_var = tk.BooleanVar(value=config.JARVIS_PROACTIVE)
        self._confirm_var = tk.BooleanVar(value=config.AGENT_CONFIRM_DANGEROUS)
        vars_map = {
            "AGENT_VOICE_FEEDBACK": self._voice_var,
            "JARVIS_PROACTIVE": self._proactive_var,
            "AGENT_CONFIRM_DANGEROUS": self._confirm_var,
        }

        for i, (label, attr) in enumerate(toggles):
            row = tk.Frame(frame, bg="#1e1e1e")
            row.pack(fill="x", pady=2)

            tk.Label(
                row,
                text=label,
                font=("Helvetica", 11),
                fg="#eeeeee",
                bg="#1e1e1e",
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            var = vars_map[attr]
            cb = tk.Checkbutton(
                row,
                variable=var,
                bg="#1e1e1e",
                fg="#4ade80",
                selectcolor="#2a2a2a",
                activebackground="#1e1e1e",
                activeforeground="#4ade80",
                command=lambda a=attr, v=var: self._on_toggle(a, v),
            )
            cb.pack(side="right")

    def _build_actions(self) -> None:
        """Action buttons."""
        frame = tk.Frame(self._root, bg="#1e1e1e")
        frame.pack(fill="x", padx=16, pady=4)

        actions = [
            ("🖥  Open Terminal Chat", self._open_terminal),
            ("📁  Open Knowledge Folder", self._open_knowledge),
            ("📄  Open Log File", self._open_log),
        ]

        for text, cmd in actions:
            btn = tk.Button(
                frame,
                text=text,
                command=cmd,
                font=("Helvetica", 10),
                fg="#ffffff",
                bg="#333333",
                activebackground="#444444",
                activeforeground="#ffffff",
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=12,
                pady=6,
                anchor="w",
            )
            btn.pack(fill="x", pady=2)
            # Hover effect
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg="#444444"))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg="#333333"))

    def _build_footer(self) -> None:
        """Bottom section with Quit button."""
        frame = tk.Frame(self._root, bg="#1e1e1e")
        frame.pack(fill="x", padx=16, pady=(4, 12))

        quit_btn = tk.Button(
            frame,
            text="✕  Quit AILIEN",
            command=self._quit,
            font=("Helvetica", 10, "bold"),
            fg="#ef4444",
            bg="#2a2a2a",
            activebackground="#3a2020",
            activeforeground="#ef4444",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=6,
        )
        quit_btn.pack(fill="x")
        quit_btn.bind("<Enter>", lambda e: quit_btn.configure(bg="#3a2020"))
        quit_btn.bind("<Leave>", lambda e: quit_btn.configure(bg="#2a2a2a"))

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_toggle(self, attr: str, var: tk.BooleanVar) -> None:
        """Update config when a toggle is clicked."""
        value = var.get()
        setattr(config, attr, value)
        logger.info("Control panel: %s set to %s", attr, value)

    def _open_terminal(self) -> None:
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

    def _open_knowledge(self) -> None:
        """Open the knowledge folder."""
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

    def _open_log(self) -> None:
        """Open the log file."""
        try:
            subprocess.Popen(
                ["xdg-open", str(config.LOG_FILE.resolve())],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.warning("Could not open log file: %s", exc)

    def _quit(self) -> None:
        """Quit the entire application."""
        logger.info("Quit requested from control panel")
        from utils.helpers import notify
        notify("AILIEN", "Agent stopped")
        self.close()
        # Signal all threads to stop via the root window
        if self._root is not None:
            try:
                self._root.quit()
            except Exception:
                pass

    def _on_close(self) -> None:
        """Hide instead of close when window X is clicked."""
        self.hide()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def put_status(self, status: str) -> None:
        """Thread-safe status update from the agent thread."""
        self._queue.put(status)

    def toggle(self) -> None:
        """Show or hide the control panel."""
        if self._root is None:
            return
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self) -> None:
        """Show the control panel."""
        if self._root is None:
            return
        self._visible = True
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()

    def hide(self) -> None:
        """Hide the control panel."""
        if self._root is None:
            return
        self._visible = False
        self._root.withdraw()

    @property
    def is_visible(self) -> bool:
        return self._visible

    def _update_status(self, status: str) -> None:
        """Update the status display."""
        self._status = status
        color = STATUS_COLORS.get(status, "#808080")
        text = STATUS_LABELS.get(status, status.capitalize())

        if self._indicator and self._indicator_dot is not None:
            try:
                self._indicator.itemconfig(self._indicator_dot, fill=color)
            except Exception:
                pass
        if self._status_label:
            try:
                self._status_label.config(text=text)
            except Exception:
                pass

    def _poll_queue(self) -> None:
        """Poll the status update queue from the tkinter main loop."""
        if self._root is None:
            return
        try:
            while True:
                status = self._queue.get_nowait()
                self._update_status(status)
        except Empty:
            pass
        if self._root is not None:
            try:
                self._root.after(100, self._poll_queue)
            except Exception:
                pass

    def close(self) -> None:
        """Destroy the window and clean up."""
        if self._root is None:
            return
        try:
            self._root.destroy()
        except Exception:
            pass
        self._root = None
