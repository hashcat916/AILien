"""Floating GUI overlay showing agent status."""
import logging
import threading
from queue import Empty, Queue

try:
    import tkinter as tk
except ImportError:
    tk = None  # type: ignore

logger = logging.getLogger("agent")

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


class StatusOverlay:
    """A small always-on-top overlay showing the agent's current status."""

    def __init__(self, width: int = 220, height: int = 70) -> None:
        if tk is None:
            raise RuntimeError("tkinter is not available")
        self._queue: Queue[str] = Queue()
        self._current_status = "idle"
        self._width = width
        self._height = height
        self._root: tk.Tk | None = None
        self._canvas: tk.Canvas | None = None
        self._indicator: int | None = None
        self._label: tk.Label | None = None
        self._agent_thread: threading.Thread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self._root = tk.Tk()
        self._root.title("AILIEN")
        self._root.geometry(f"{self._width}x{self._height}+20+20")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.configure(bg="#1e1e1e")

        # Drag support
        self._offset_x = 0
        self._offset_y = 0
        self._root.bind("<Button-1>", self._on_click)
        self._root.bind("<B1-Motion>", self._on_drag)

        # Close button (small X in top-right)
        close_btn = tk.Label(
            self._root,
            text="×",
            font=("Helvetica", 14),
            fg="#ef4444",
            bg="#1e1e1e",
            cursor="hand2",
        )
        close_btn.place(relx=1.0, x=-4, y=2, anchor="ne")
        close_btn.bind("<Button-1>", lambda e: self.close())

        # Status indicator circle
        self._canvas = tk.Canvas(
            self._root,
            width=28,
            height=28,
            bg="#1e1e1e",
            highlightthickness=0,
        )
        self._canvas.place(x=12, y=20)
        self._indicator = self._canvas.create_oval(
            4, 4, 24, 24, fill=STATUS_COLORS["idle"], outline=""
        )

        # Status text
        self._label = tk.Label(
            self._root,
            text=STATUS_LABELS["idle"],
            font=("Helvetica", 14, "bold"),
            fg="#ffffff",
            bg="#1e1e1e",
        )
        self._label.place(x=48, y=22)

        # Start polling the queue
        self._poll_queue()

    def _on_click(self, event: tk.Event) -> None:  # type: ignore
        self._offset_x = event.x
        self._offset_y = event.y

    def _on_drag(self, event: tk.Event) -> None:  # type: ignore
        if self._root:
            x = self._root.winfo_pointerx() - self._offset_x
            y = self._root.winfo_pointery() - self._offset_y
            self._root.geometry(f"+{x}+{y}")

    def _update_status(self, status: str) -> None:
        if status == "closed":
            self.close()
            return
        self._current_status = status
        color = STATUS_COLORS.get(status, "#808080")
        text = STATUS_LABELS.get(status, status.capitalize())
        if self._canvas and self._indicator is not None:
            self._canvas.itemconfig(self._indicator, fill=color)
        if self._label:
            self._label.config(text=text)

    def _poll_queue(self) -> None:
        if self._root is None:
            return
        try:
            while True:
                status = self._queue.get_nowait()
                self._update_status(status)
                if self._root is None:
                    return
        except Empty:
            pass
        if self._root is not None:
            self._root.after(50, self._poll_queue)

    def put_status(self, status: str) -> None:
        """Thread-safe status update from the agent thread."""
        self._queue.put(status)

    def start_agent(self, target: callable) -> None:  # type: ignore
        """Start the agent logic in a background thread."""
        self._agent_thread = threading.Thread(target=target, daemon=True)
        self._agent_thread.start()

    def show(self) -> None:
        """Show the overlay window."""
        if self._root:
            self._root.deiconify()

    def hide(self) -> None:
        """Hide the overlay window."""
        if self._root:
            self._root.withdraw()

    def close(self) -> None:
        """Close the overlay and signal the agent to stop."""
        if self._root:
            try:
                self._root.destroy()
            except tk.TclError:
                pass
            self._root = None

    def run(self) -> None:
        """Run the tkinter mainloop. Must be called on the main thread."""
        if self._root:
            self._root.mainloop()
