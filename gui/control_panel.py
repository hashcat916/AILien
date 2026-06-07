"""Floating control panel — compact settings and status for AILIEN.

Opened from the tray icon. Shows agent status, toggles for features,
and quick action buttons. Thread-safe via queue.
"""

import logging
import os
import subprocess
import threading
from queue import Empty, Queue

import config

logger = logging.getLogger("agent")

try:
    import tkinter as tk
except ImportError:
    tk = None

BG_DARK      = "#0d1117"
BG_MEDIUM    = "#161b22"
BG_LIGHT     = "#21262d"
FG_PRIMARY   = "#e6edf3"
FG_SECONDARY = "#8b949e"
FG_ACCENT    = "#58a6ff"
FG_GREEN     = "#3fb950"
FG_RED       = "#f85149"
BORDER       = "#30363d"

STATUS_COLORS = {
    "idle":      "#8b949e",
    "listening": "#3fb950",
    "thinking":  "#d29922",
    "speaking":  "#58a6ff",
    "closed":    "#8b949e",
}
STATUS_LABELS = {
    "idle": "Idle", "listening": "Listening...",
    "thinking": "Thinking...", "speaking": "Speaking...",
    "closed": "",
}


class ControlPanel:
    """Compact floating control panel."""

    def __init__(self) -> None:
        if tk is None:
            raise RuntimeError("tkinter not available")
        self._queue: Queue[str] = Queue()
        self._status = "idle"
        self._visible = False
        self._root: tk.Tk | None = None
        self._dot: int | None = None
        self._status_label: tk.Label | None = None
        self._canvas: tk.Canvas | None = None
        self._voice_var = tk.BooleanVar(value=config.AGENT_VOICE_FEEDBACK)
        self._proactive_var = tk.BooleanVar(value=config.JARVIS_PROACTIVE)
        self._confirm_var = tk.BooleanVar(value=config.AGENT_CONFIRM_DANGEROUS)
        self._thread = threading.Thread(target=self._build_ui, daemon=True)
        self._thread.start()

    def _build_ui(self) -> None:
        self._root = tk.Tk()
        self._root.title("AILIEN Control Panel")
        self._root.configure(bg=BG_DARK)
        self._root.attributes("-topmost", True)
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        sw = self._root.winfo_screenwidth()
        self._root.geometry(f"300x340+{sw - 340}+60")

        # Title
        header = tk.Label(self._root, text="👽  AILIEN",
                          font=("Segoe UI", 15, "bold"),
                          fg=FG_GREEN, bg=BG_DARK)
        header.pack(fill="x", padx=16, pady=(14, 4))

        # Status
        row = tk.Frame(self._root, bg=BG_DARK)
        row.pack(fill="x", padx=16, pady=(4, 8))

        self._canvas = tk.Canvas(row, width=18, height=18,
                                 bg=BG_DARK, highlightthickness=0)
        self._canvas.pack(side="left", padx=(0, 8))
        self._dot = self._canvas.create_oval(2, 2, 16, 16,
                                              fill=STATUS_COLORS["idle"],
                                              outline="")

        self._status_label = tk.Label(row, text="Idle",
                                      font=("Segoe UI", 11),
                                      fg=FG_PRIMARY, bg=BG_DARK)
        self._status_label.pack(side="left")

        # Separator
        tk.Frame(self._root, height=1, bg=BORDER).pack(fill="x", padx=16, pady=6)

        # Toggles
        toggles_frame = tk.Frame(self._root, bg=BG_DARK)
        toggles_frame.pack(fill="x", padx=16, pady=4)

        for label, var in [
            ("Voice Feedback", self._voice_var),
            ("Proactive Alerts", self._proactive_var),
            ("Confirm Dangerous", self._confirm_var),
        ]:
            row = tk.Frame(toggles_frame, bg=BG_DARK)
            row.pack(fill="x", pady=3)

            tk.Label(row, text=label, font=("Segoe UI", 10),
                     fg=FG_PRIMARY, bg=BG_DARK, anchor="w"
                     ).pack(side="left", fill="x", expand=True)

            self._make_toggle(row, var)

        # Separator
        tk.Frame(self._root, height=1, bg=BORDER).pack(fill="x", padx=16, pady=6)

        # Actions
        actions_frame = tk.Frame(self._root, bg=BG_DARK)
        actions_frame.pack(fill="x", padx=16, pady=4)

        for text, cmd in [
            ("🖥  Open Terminal Chat", self._open_terminal),
            ("📁  Knowledge Folder", self._open_knowledge),
            ("📄  Open Log File", self._open_log),
        ]:
            btn = tk.Label(actions_frame, text=text,
                           font=("Segoe UI", 10),
                           fg=FG_PRIMARY, bg=BG_LIGHT,
                           cursor="hand2", padx=12, pady=6,
                           anchor="w")
            btn.pack(fill="x", pady=2)
            btn.bind("<Button-1>", lambda e, c=cmd: c())
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=BG_MEDIUM))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=BG_LIGHT))

        # Quit button
        tk.Frame(self._root, height=1, bg=BORDER).pack(fill="x", padx=16, pady=6)

        quit_btn = tk.Label(self._root, text="✕  Quit AILIEN",
                            font=("Segoe UI", 10, "bold"),
                            fg=FG_RED, bg="#1a1a1a",
                            cursor="hand2", padx=12, pady=8,
                            anchor="center")
        quit_btn.pack(fill="x", padx=16, pady=(4, 12))
        quit_btn.bind("<Button-1>", lambda e: self._quit())
        quit_btn.bind("<Enter>", lambda e: quit_btn.configure(bg="#2a1515"))
        quit_btn.bind("<Leave>", lambda e: quit_btn.configure(bg="#1a1a1a"))

        self._root.withdraw()
        self._poll_queue()
        self._root.mainloop()

    def _make_toggle(self, parent, var):
        canvas = tk.Canvas(parent, width=30, height=16,
                           bg=BG_DARK, highlightthickness=0, cursor="hand2")
        canvas.pack(side="right")

        def redraw():
            canvas.delete("all")
            on = var.get()
            bg = "#3fb950" if on else "#30363d"
            knob = 15 if on else 3
            canvas.create_oval(0, 0, 30, 16, fill=bg, outline="")
            canvas.create_oval(knob, 1, knob + 13, 15,
                               fill="#ffffff", outline="")

        def click(e):
            var.set(not var.get())
            self._on_toggle(var)
            redraw()

        canvas.bind("<Button-1>", click)
        redraw()

    def _on_toggle(self, var):
        mapping = {
            id(self._voice_var): ("AGENT_VOICE_FEEDBACK", self._voice_var),
            id(self._proactive_var): ("JARVIS_PROACTIVE", self._proactive_var),
            id(self._confirm_var): ("AGENT_CONFIRM_DANGEROUS", self._confirm_var),
        }
        for vid, (attr, v) in mapping.items():
            if id(var) == vid:
                setattr(config, attr, v.get())
                logger.info("Control panel: %s → %s", attr, v.get())
                break

    def _open_terminal(self):
        try:
            term = os.environ.get("TERMINAL", os.environ.get("TERM", "x-terminal-emulator"))
            subprocess.Popen([term, "-e",
                             f"bash -c 'cd {config.PROJECT_DIR} && .venv/bin/python3 main.py --text; exec bash'"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            logger.warning("Open terminal failed: %s", exc)

    def _open_knowledge(self):
        try:
            d = config.PROJECT_DIR / "knowledge"
            d.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["xdg-open", str(d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            logger.warning("Open knowledge failed: %s", exc)

    def _open_log(self):
        try:
            subprocess.Popen(["xdg-open", str(config.LOG_FILE.resolve())],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            logger.warning("Open log failed: %s", exc)

    def _quit(self):
        logger.info("Quit from control panel")
        from utils.helpers import notify
        notify("AILIEN", "Agent stopped")
        self.close()

    def _on_close(self):
        self.hide()

    def put_status(self, status: str) -> None:
        self._queue.put(status)

    def toggle(self) -> None:
        if self._root is None:
            return
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self) -> None:
        if self._root:
            self._visible = True
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()

    def hide(self) -> None:
        if self._root:
            self._visible = False
            self._root.withdraw()

    @property
    def is_visible(self) -> bool:
        return self._visible

    def _update_status(self, status: str) -> None:
        self._status = status
        color = STATUS_COLORS.get(status, "#8b949e")
        text = STATUS_LABELS.get(status, status.capitalize())
        if self._canvas and self._dot is not None:
            try:
                self._canvas.itemconfig(self._dot, fill=color)
            except Exception:
                pass
        if self._status_label:
            try:
                self._status_label.config(text=text)
            except Exception:
                pass

    def _poll_queue(self) -> None:
        if self._root is None:
            return
        try:
            while True:
                self._update_status(self._queue.get_nowait())
        except Empty:
            pass
        if self._root:
            try:
                self._root.after(100, self._poll_queue)
            except Exception:
                pass

    def close(self) -> None:
        if self._root:
            try:
                self._root.destroy()
            except Exception:
                pass
            self._root = None
