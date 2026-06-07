"""Voice Control Window — the main GUI for AILIEN.

A proper window interface with:
- Big START/PAUSE button for voice control
- STOP button to interrupt mid-sentence
- Text input field for typing commands
- Scrollable conversation log
- Status indicator with color
- Toggle switches for settings
- Clean dark theme

Replaces the tiny StatusOverlay as the primary interface.
"""

import logging
import os
import subprocess
import threading
import time
from queue import Empty, Queue
from typing import Callable

import config

logger = logging.getLogger("agent")

try:
    import tkinter as tk
    from tkinter import scrolledtext, font
except ImportError:
    tk = None  # type: ignore

STATUS_COLORS = {
    "idle": "#808080",
    "listening": "#4ade80",
    "thinking": "#fbbf24",
    "speaking": "#60a5fa",
    "error": "#ef4444",
    "closed": "#808080",
}

STATUS_LABELS = {
    "idle": "Idle",
    "listening": "Listening...",
    "thinking": "Thinking...",
    "speaking": "Speaking...",
    "error": "Error",
    "closed": "",
}

# Background colors
BG_DARK = "#1a1a2e"
BG_MEDIUM = "#16213e"
BG_LIGHT = "#1c2a4a"
BG_INPUT = "#0f3460"
FG_PRIMARY = "#e0e0e0"
FG_SECONDARY = "#a0a0a0"
FG_ACCENT = "#4ade80"
FG_RED = "#ef4444"
FG_BLUE = "#60a5fa"
FG_YELLOW = "#fbbf24"
BORDER_COLOR = "#2a2a4a"


class VoiceWindow:
    """Full voice control window for AILIEN.

    Runs its own tkinter mainloop on a background thread.
    Thread-safe status and message updates via queues.
    """

    def __init__(self, agent_ref: object = None) -> None:
        if tk is None:
            raise RuntimeError("tkinter is not available")

        self._status_queue: Queue[str] = Queue()
        self._message_queue: Queue[tuple[str, str]] = Queue()  # (role, text)
        self._command_queue: Queue[str] = Queue()  # Commands back to agent
        self._status = "idle"
        self._visible = False
        self._voice_active = False
        self._agent_ref = agent_ref
        self._root: tk.Tk | None = None
        self._input_callback: Callable[[str], None] | None = None
        self._stop_callback: Callable[[], None] | None = None
        self._voice_toggle_callback: Callable[[bool], None] | None = None
        self._voice_lock = threading.Lock()

        # Widget references
        self._status_indicator: tk.Canvas | None = None
        self._status_dot: int | None = None
        self._status_label: tk.Label | None = None
        self._voice_btn: tk.Button | None = None
        self._stop_btn: tk.Button | None = None
        self._input_entry: tk.Entry | None = None
        self._send_btn: tk.Button | None = None
        self._log: scrolledtext.ScrolledText | None = None
        self._voice_var: tk.BooleanVar | None = None
        self._proactive_var: tk.BooleanVar | None = None
        self._confirm_var: tk.BooleanVar | None = None

        self._thread = threading.Thread(target=self._build_ui, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Public API — thread-safe
    # ------------------------------------------------------------------

    def put_status(self, status: str) -> None:
        """Thread-safe status update from the agent thread."""
        self._status_queue.put(status)

    def append_message(self, role: str, text: str) -> None:
        """Thread-safe message append from the agent thread."""
        self._message_queue.put((role, text))

    def set_voice_active(self, active: bool) -> None:
        """Thread-safe way to set voice active state from any thread.

        Updates the button text/color and toggles the internal state
        without directly touching tkinter widgets (uses the status queue).
        """
        with self._voice_lock:
            self._voice_active = active
        if active:
            self.append_message("system", "Voice listening active.")
            # Schedule the button update via the tkinter poll loop
            self._status_queue.put("_voice_on")
        else:
            self.append_message("system", "Voice listening paused.")
            self._status_queue.put("_voice_off")

    def set_callbacks(
        self,
        on_command: Callable[[str], None] | None = None,
        on_stop: Callable[[], None] | None = None,
        on_voice_toggle: Callable[[bool], None] | None = None,
    ) -> None:
        """Set callbacks for command submission, stop, and voice toggle."""
        self._input_callback = on_command
        self._stop_callback = on_stop
        self._voice_toggle_callback = on_voice_toggle

    def show(self) -> None:
        """Show the window."""
        if self._root:
            self._visible = True
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()

    def hide(self) -> None:
        """Hide the window."""
        if self._root:
            self._visible = False
            self._root.withdraw()

    def toggle(self) -> None:
        """Show or hide."""
        if self._visible:
            self.hide()
        else:
            self.show()

    def close(self) -> None:
        """Destroy the window."""
        if self._root:
            try:
                self._root.destroy()
            except Exception:
                pass
            self._root = None

    @property
    def is_visible(self) -> bool:
        return self._visible

    @property
    def voice_active(self) -> bool:
        with self._voice_lock:
            return self._voice_active

    # ------------------------------------------------------------------
    # UI Building
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Create the tkinter window."""
        self._root = tk.Tk()
        self._root.title("AILIEN Voice Control")
        self._root.configure(bg=BG_DARK)
        self._root.attributes("-topmost", True)
        self._root.resizable(True, True)
        self._root.minsize(500, 500)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Position centered on screen
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        w, h = 520, 640
        self._root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Custom fonts
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(size=10)

        # Configure grid weights
        self._root.grid_rowconfigure(2, weight=1)  # log area expands
        self._root.grid_columnconfigure(0, weight=1)

        # ---- Build sections ----
        self._build_header()
        self._build_status_bar()
        self._build_log_area()
        self._build_input_area()
        self._build_toggle_bar()
        self._build_action_buttons()

        # Start hidden
        self._root.withdraw()

        # Start polling queues
        self._poll_queues()
        self._root.mainloop()

    def _build_header(self) -> None:
        """Top header bar with title and close button."""
        frame = tk.Frame(self._root, bg=BG_MEDIUM, height=48)
        frame.grid(row=0, column=0, sticky="ew")
        frame.grid_propagate(False)

        # Alien icon + title
        title = tk.Label(
            frame,
            text="👽  AILIEN — Voice Control",
            font=("Helvetica", 14, "bold"),
            fg=FG_ACCENT,
            bg=BG_MEDIUM,
        )
        title.pack(side="left", padx=16, pady=10)

        # Close button
        close_btn = tk.Label(
            frame,
            text="✕",
            font=("Helvetica", 16),
            fg=FG_SECONDARY,
            bg=BG_MEDIUM,
            cursor="hand2",
        )
        close_btn.pack(side="right", padx=12)
        close_btn.bind("<Button-1>", lambda e: self.hide())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=FG_RED))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=FG_SECONDARY))

    def _build_status_bar(self) -> None:
        """Status bar with indicator dot, status text, and voice/stop buttons."""
        frame = tk.Frame(self._root, bg=BG_DARK, height=60)
        frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 4))
        frame.grid_propagate(False)
        frame.grid_columnconfigure(1, weight=1)

        # Status indicator
        status_frame = tk.Frame(frame, bg=BG_DARK)
        status_frame.grid(row=0, column=0, sticky="w")

        self._status_indicator = tk.Canvas(
            status_frame, width=20, height=20,
            bg=BG_DARK, highlightthickness=0,
        )
        self._status_indicator.pack(side="left", padx=(0, 8))
        self._status_dot = self._status_indicator.create_oval(
            2, 2, 18, 18, fill=STATUS_COLORS["idle"], outline="",
        )

        self._status_label = tk.Label(
            status_frame,
            text=STATUS_LABELS["idle"],
            font=("Helvetica", 12, "bold"),
            fg=FG_PRIMARY,
            bg=BG_DARK,
        )
        self._status_label.pack(side="left")

        # Voice toggle button (big round style)
        self._voice_btn = tk.Button(
            frame,
            text="▶  LISTEN",
            font=("Helvetica", 11, "bold"),
            fg="#ffffff",
            bg=FG_ACCENT,
            activebackground="#3cb371",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=20,
            pady=8,
            command=self._toggle_voice,
        )
        self._voice_btn.grid(row=0, column=1, padx=(0, 8))

        # Stop button
        self._stop_btn = tk.Button(
            frame,
            text="⏹  STOP",
            font=("Helvetica", 11, "bold"),
            fg="#ffffff",
            bg=FG_RED,
            activebackground="#cc3333",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=16,
            pady=8,
            state="disabled",
            command=self._on_stop,
        )
        self._stop_btn.grid(row=0, column=2)

    def _build_log_area(self) -> None:
        """Scrollable conversation log."""
        frame = tk.Frame(self._root, bg=BG_DARK)
        frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=4)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        self._log = scrolledtext.ScrolledText(
            frame,
            wrap="word",
            font=("Consolas", 10),
            bg=BG_MEDIUM,
            fg=FG_PRIMARY,
            insertbackground=FG_ACCENT,
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
            state="disabled",
            height=20,
        )
        self._log.grid(row=0, column=0, sticky="nsew")

        # Configure tag styles
        self._log.tag_configure("user", foreground="#88ccff", font=("Consolas", 10, "bold"))
        self._log.tag_configure("agent", foreground=FG_ACCENT)
        self._log.tag_configure("info", foreground=FG_SECONDARY, font=("Consolas", 9))
        self._log.tag_configure("error", foreground=FG_RED)
        self._log.tag_configure("system", foreground=FG_YELLOW, font=("Consolas", 9, "italic"))

    def _build_input_area(self) -> None:
        """Text input field with send button."""
        frame = tk.Frame(self._root, bg=BG_DARK, height=50)
        frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 8))
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, weight=1)

        self._input_entry = tk.Entry(
            frame,
            font=("Helvetica", 11),
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_ACCENT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=FG_ACCENT,
        )
        self._input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._input_entry.bind("<Return>", self._on_send)

        self._send_btn = tk.Button(
            frame,
            text="Send",
            font=("Helvetica", 10, "bold"),
            fg="#ffffff",
            bg=FG_BLUE,
            activebackground="#4a90d9",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=16,
            pady=6,
            command=self._on_send,
        )
        self._send_btn.grid(row=0, column=1)

    def _build_toggle_bar(self) -> None:
        """Toggle switches for voice feedback, proactive, confirm dangerous."""
        frame = tk.Frame(self._root, bg=BG_DARK)
        frame.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 2))

        # Voice feedback toggle
        voice_frame = tk.Frame(frame, bg=BG_DARK)
        voice_frame.pack(side="left", padx=(0, 16))
        voice_lbl = tk.Label(
            voice_frame, text="Voice", font=("Helvetica", 9),
            fg=FG_SECONDARY, bg=BG_DARK,
        )
        voice_lbl.pack(side="left", padx=(0, 4))
        self._voice_var = tk.BooleanVar(value=config.AGENT_VOICE_FEEDBACK)
        voice_cb = tk.Checkbutton(
            voice_frame, variable=self._voice_var,
            bg=BG_DARK, fg=FG_ACCENT, selectcolor=BG_INPUT,
            activebackground=BG_DARK, activeforeground=FG_ACCENT,
            command=lambda: self._on_toggle("AGENT_VOICE_FEEDBACK", self._voice_var),
        )
        voice_cb.pack(side="left")

        # Proactive toggle
        pro_frame = tk.Frame(frame, bg=BG_DARK)
        pro_frame.pack(side="left", padx=(0, 16))
        pro_lbl = tk.Label(
            pro_frame, text="Proactive", font=("Helvetica", 9),
            fg=FG_SECONDARY, bg=BG_DARK,
        )
        pro_lbl.pack(side="left", padx=(0, 4))
        self._proactive_var = tk.BooleanVar(value=config.JARVIS_PROACTIVE)
        pro_cb = tk.Checkbutton(
            pro_frame, variable=self._proactive_var,
            bg=BG_DARK, fg=FG_ACCENT, selectcolor=BG_INPUT,
            activebackground=BG_DARK, activeforeground=FG_ACCENT,
            command=lambda: self._on_toggle("JARVIS_PROACTIVE", self._proactive_var),
        )
        pro_cb.pack(side="left")

        # Confirm dangerous toggle
        conf_frame = tk.Frame(frame, bg=BG_DARK)
        conf_frame.pack(side="left")
        conf_lbl = tk.Label(
            conf_frame, text="Confirm", font=("Helvetica", 9),
            fg=FG_SECONDARY, bg=BG_DARK,
        )
        conf_lbl.pack(side="left", padx=(0, 4))
        self._confirm_var = tk.BooleanVar(value=config.AGENT_CONFIRM_DANGEROUS)
        conf_cb = tk.Checkbutton(
            conf_frame, variable=self._confirm_var,
            bg=BG_DARK, fg=FG_ACCENT, selectcolor=BG_INPUT,
            activebackground=BG_DARK, activeforeground=FG_ACCENT,
            command=lambda: self._on_toggle("AGENT_CONFIRM_DANGEROUS", self._confirm_var),
        )
        conf_cb.pack(side="left")

    def _build_action_buttons(self) -> None:
        """Quick action buttons at the bottom."""
        frame = tk.Frame(self._root, bg=BG_DARK, height=40)
        frame.grid(row=5, column=0, sticky="ew", padx=16, pady=(2, 12))
        frame.grid_propagate(False)

        def _make_action_btn(text: str, command: Callable) -> tk.Button:
            btn = tk.Button(
                frame,
                text=text,
                command=command,
                font=("Helvetica", 9),
                fg=FG_PRIMARY,
                bg=BG_LIGHT,
                activebackground=BG_INPUT,
                activeforeground=FG_PRIMARY,
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=10,
                pady=4,
            )
            btn.pack(side="left", padx=(0, 6))
            btn.bind("<Enter>", lambda e: btn.configure(bg=BG_INPUT))
            btn.bind("<Leave>", lambda e: btn.configure(bg=BG_LIGHT))
            return btn

        _make_action_btn("🖥  Screenshot", self._on_screenshot)
        _make_action_btn("📁  Knowledge", self._on_open_knowledge)
        _make_action_btn("📄  Log", self._on_open_log)
        _make_action_btn("🗑  Clear", self._on_clear)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _toggle_voice(self) -> None:
        """Toggle voice listening on/off.

        Updates the button state and call ``on_voice_toggle`` callback
        (if set) so the agent can start/stop the wake word detector.
        """
        with self._voice_lock:
            self._voice_active = not self._voice_active
            active = self._voice_active
        if active:
            self._voice_btn.config(text="⏸  PAUSE", bg=FG_YELLOW)
            self.append_message("system", "Voice listening active.")
        else:
            self._voice_btn.config(text="▶  LISTEN", bg=FG_ACCENT)
            self.append_message("system", "Voice listening paused.")

        # Notify the agent to start/stop the detector
        if self._voice_toggle_callback:
            self._voice_toggle_callback(active)

    def _on_stop(self) -> None:
        """Stop the current action mid-sentence/processing."""
        if self._stop_callback:
            self._stop_callback()
        self.put_status("idle")
        self._enable_stop_button(False)

    def _on_send(self, event=None) -> None:
        """Send text from input field."""
        if not self._input_entry:
            return
        text = self._input_entry.get().strip()
        if not text:
            return
        self._input_entry.delete(0, tk.END)
        self._submit_command(text)

    def _submit_command(self, text: str) -> None:
        """Submit a command."""
        self.append_message("user", text)
        self._enable_stop_button(True)
        self.put_status("thinking")
        if self._input_callback:
            self._input_callback(text)
        else:
            self.append_message("system", "Agent not ready yet — please wait.")

    def _on_toggle(self, attr: str, var: tk.BooleanVar) -> None:
        """Update config when a toggle is clicked."""
        setattr(config, attr, var.get())
        logger.info("Voice window toggle: %s set to %s", attr, var.get())

    def _on_screenshot(self) -> None:
        """Take a screenshot command."""
        self._submit_command("Take a screenshot and describe what you see")

    def _on_open_knowledge(self) -> None:
        """Open the knowledge folder."""
        try:
            knowledge_dir = config.PROJECT_DIR / "knowledge"
            knowledge_dir.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(
                ["xdg-open", str(knowledge_dir)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.warning("Could not open knowledge folder: %s", exc)

    def _on_open_log(self) -> None:
        """Open the log file."""
        try:
            subprocess.Popen(
                ["xdg-open", str(config.LOG_FILE.resolve())],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.warning("Could not open log file: %s", exc)

    def _on_clear(self) -> None:
        """Clear the conversation log."""
        if self._log:
            self._log.config(state="normal")
            self._log.delete(1.0, tk.END)
            self._log.config(state="disabled")

    def _on_close(self) -> None:
        """Hide instead of closing — keep running in background."""
        self.hide()

    def _enable_stop_button(self, enabled: bool) -> None:
        if self._stop_btn:
            self._stop_btn.config(state="normal" if enabled else "disabled")

    # ------------------------------------------------------------------
    # Queue Polling
    # ------------------------------------------------------------------

    def _poll_queues(self) -> None:
        """Poll status and message queues from the tkinter mainloop."""
        if self._root is None:
            return

        # Process status updates
        try:
            while True:
                status = self._status_queue.get_nowait()
                self._update_status(status)
        except Empty:
            pass

        # Process message updates
        try:
            while True:
                role, text = self._message_queue.get_nowait()
                self._append_to_log(role, text)
        except Empty:
            pass

        if self._root:
            try:
                self._root.after(100, self._poll_queues)
            except Exception:
                pass

    def _update_status(self, status: str) -> None:
        """Update the status display.

        Also handles internal commands like ``_voice_on`` / ``_voice_off``
        for thread-safe GUI updates.
        """
        # Handle internal commands first
        if status == "_voice_on":
            if self._voice_btn:
                self._voice_btn.config(text="⏸  PAUSE", bg=FG_YELLOW)
            return
        if status == "_voice_off":
            if self._voice_btn:
                self._voice_btn.config(text="▶  LISTEN", bg=FG_ACCENT)
            return

        self._status = status
        color = STATUS_COLORS.get(status, STATUS_COLORS["idle"])
        text = STATUS_LABELS.get(status, status.capitalize())

        if self._status_indicator and self._status_dot is not None:
            try:
                self._status_indicator.itemconfig(self._status_dot, fill=color)
            except Exception:
                pass
        if self._status_label:
            try:
                self._status_label.config(text=text)
            except Exception:
                pass

        # Enable stop button when thinking, speaking, or listening
        if status in ("thinking", "speaking", "listening"):
            self._enable_stop_button(True)
        else:
            self._enable_stop_button(False)

        # Update window title
        if self._root:
            try:
                self._root.title(f"AILIEN — {text}")
            except Exception:
                pass

    def _append_to_log(self, role: str, text: str) -> None:
        """Append a message to the conversation log."""
        if not self._log:
            return

        tag = role if role in ("user", "agent", "info", "error", "system") else "info"

        try:
            self._log.config(state="normal")

            if tag == "user":
                self._log.insert(tk.END, f"You: {text}\n\n", tag)
            elif tag == "agent":
                self._log.insert(tk.END, f"AILIEN: {text}\n\n", tag)
            elif tag == "system":
                self._log.insert(tk.END, f"── {text} ──\n\n", tag)
            elif tag == "error":
                self._log.insert(tk.END, f"⚠ {text}\n\n", tag)
            else:
                self._log.insert(tk.END, f"{text}\n\n", tag)

            # Auto-scroll to bottom
            self._log.see(tk.END)
            self._log.config(state="disabled")
        except Exception:
            pass
