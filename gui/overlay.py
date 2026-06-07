"""Floating status overlay — small always-on-top window showing agent status.

Used in daemon mode as a minimal status indicator.
Thread-safe via queue.
"""

import logging
import threading
from queue import Empty, Queue

try:
    import tkinter as tk
except ImportError:
    tk = None

logger = logging.getLogger("agent")

BG_DARK      = "#0d1117"
FG_PRIMARY   = "#e6edf3"
FG_SECONDARY = "#8b949e"

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


class StatusOverlay:
    """Small always-on-top overlay showing agent status."""

    def __init__(self, width: int = 200, height: int = 56) -> None:
        if tk is None:
            raise RuntimeError("tkinter not available")
        self._queue: Queue[str] = Queue()
        self._width = width
        self._height = height
        self._root: tk.Tk | None = None
        self._canvas: tk.Canvas | None = None
        self._dot: int | None = None
        self._label: tk.Label | None = None
        self._thread_run = True
        self._build_ui()

    def _build_ui(self) -> None:
        self._root = tk.Tk()
        self._root.title("AILIEN")
        self._root.geometry(f"{self._width}x{self._height}+20+20")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.configure(bg=BG_DARK)

        # Drag support
        ox, oy = 0, 0
        def on_down(e):
            nonlocal ox, oy
            ox, oy = e.x, e.y
        def on_move(e):
            if self._root:
                self._root.geometry(f"+{e.x_root - ox}+{e.y_root - oy}")
        self._root.bind("<Button-1>", on_down)
        self._root.bind("<B1-Motion>", on_move)

        # Close button
        close = tk.Label(self._root, text="×", font=("Segoe UI", 13),
                         fg=FG_SECONDARY, bg=BG_DARK, cursor="hand2")
        close.place(relx=1.0, x=-6, y=0, anchor="ne")
        close.bind("<Button-1>", lambda e: self.close())
        close.bind("<Enter>", lambda e: close.configure(fg="#f85149"))
        close.bind("<Leave>", lambda e: close.configure(fg=FG_SECONDARY))

        # Status indicator
        self._canvas = tk.Canvas(self._root, width=18, height=18,
                                 bg=BG_DARK, highlightthickness=0)
        self._canvas.place(x=12, y=18)
        self._dot = self._canvas.create_oval(1, 1, 17, 17,
                                              fill=STATUS_COLORS["idle"],
                                              outline="")

        self._label = tk.Label(self._root, text=STATUS_LABELS["idle"],
                               font=("Segoe UI", 12, "bold"),
                               fg=FG_PRIMARY, bg=BG_DARK)
        self._label.place(x=38, y=17)

        self._poll_queue()

    def _update_status(self, status: str) -> None:
        if status == "closed":
            self.close()
            return
        color = STATUS_COLORS.get(status, "#8b949e")
        text = STATUS_LABELS.get(status, status.capitalize())
        if self._canvas and self._dot is not None:
            try:
                self._canvas.itemconfig(self._dot, fill=color)
            except Exception:
                pass
        if self._label:
            try:
                self._label.config(text=text)
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

    def put_status(self, status: str) -> None:
        self._queue.put(status)

    def start_agent(self, target) -> None:
        t = threading.Thread(target=target, daemon=True)
        t.start()

    def show(self) -> None:
        if self._root:
            self._root.deiconify()

    def hide(self) -> None:
        if self._root:
            self._root.withdraw()

    def close(self) -> None:
        if self._root:
            try:
                self._root.destroy()
            except tk.TclError:
                pass
            self._root = None

    def run(self) -> None:
        if self._root:
            self._root.mainloop()
