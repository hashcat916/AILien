"""Voice Control Window — professional GUI for AILIEN.

A polished tkinter window with:
- Custom draggable title bar (no OS chrome)
- Chat bubble messages (user right, agent left)
- Animated glowing status indicator
- Modern dark theme with neon accents
- Clean toggle switches
- Quick action buttons with icons

Runs its own tkinter mainloop on a background thread.
Thread-safe via queues.
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
    from tkinter import font as tkfont
except ImportError:
    tk = None

# ── Color Palette ──────────────────────────────────────────────
BG_DARK        = "#0d1117"
BG_MEDIUM      = "#161b22"
BG_LIGHT       = "#21262d"
BG_INPUT       = "#0d1117"
BG_BUBBLE_USER = "#1f6feb"
BG_BUBBLE_AI   = "#21262d"
FG_PRIMARY     = "#e6edf3"
FG_SECONDARY   = "#8b949e"
FG_ACCENT      = "#58a6ff"
FG_GREEN       = "#3fb950"
FG_YELLOW      = "#d29922"
FG_RED         = "#f85149"
BORDER_COLOR   = "#30363d"
TITLE_BG       = "#161b22"

STATUS_COLORS = {
    "idle":      "#8b949e",  # gray
    "listening": "#3fb950",  # green
    "thinking":  "#d29922",  # yellow
    "speaking":  "#58a6ff",  # blue
    "error":     "#f85149",  # red
    "closed":    "#8b949e",
}

STATUS_LABELS = {
    "idle":      "Idle",
    "listening": "Listening...",
    "thinking":  "Thinking...",
    "speaking":  "Speaking...",
    "error":     "Error",
    "closed":    "",
}


class VoiceWindow:
    """Professional voice control window for AILIEN."""

    def __init__(self, agent_ref: object = None) -> None:
        if tk is None:
            raise RuntimeError("tkinter is not available")

        self._status_queue: Queue[str] = Queue()
        self._message_queue: Queue[tuple[str, str]] = Queue()
        self._status = "idle"
        self._visible = False
        self._voice_active = False
        self._agent_ref = agent_ref
        self._root: tk.Tk | None = None
        self._input_callback: Callable[[str], None] | None = None
        self._stop_callback: Callable[[], None] | None = None
        self._voice_toggle_callback: Callable[[bool], None] | None = None
        self._voice_lock = threading.Lock()
        self._drag_data = {"x": 0, "y": 0}

        # Widget references
        self._indicator_canvas: tk.Canvas | None = None
        self._indicator_dot: int | None = None
        self._status_label: tk.Label | None = None
        self._listen_btn: tk.Canvas | None = None
        self._stop_btn: tk.Button | None = None
        self._log_frame: tk.Frame | None = None
        self._log_canvas: tk.Canvas | None = None
        self._log_inner: tk.Frame | None = None
        self._input_entry: tk.Text | None = None
        self._send_btn: tk.Canvas | None = None
        self._voice_var: tk.BooleanVar | None = None
        self._proactive_var: tk.BooleanVar | None = None
        self._confirm_var: tk.BooleanVar | None = None
        self._anim_after_id = None

        self._thread = threading.Thread(target=self._build_ui, daemon=True)
        self._thread.start()

    # ── Public API (thread-safe) ─────────────────────────────────

    def put_status(self, status: str) -> None:
        self._status_queue.put(status)

    def append_message(self, role: str, text: str) -> None:
        self._message_queue.put((role, text))

    def set_voice_active(self, active: bool) -> None:
        with self._voice_lock:
            self._voice_active = active
        self._status_queue.put("_voice_on" if active else "_voice_off")

    def set_callbacks(self, on_command=None, on_stop=None, on_voice_toggle=None) -> None:
        self._input_callback = on_command
        self._stop_callback = on_stop
        self._voice_toggle_callback = on_voice_toggle

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

    def toggle(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()

    def close(self) -> None:
        if self._anim_after_id and self._root:
            try:
                self._root.after_cancel(self._anim_after_id)
            except Exception:
                pass
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

    # ── UI Building ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._root = tk.Tk()
        self._root.title("AILIEN")
        self._root.configure(bg=BG_DARK)
        self._root.overrideredirect(True)          # remove OS chrome
        self._root.attributes("-topmost", True)
        self._root.resizable(True, True)
        self._root.minsize(420, 520)

        # Geometry
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        w, h = 520, 660
        self._root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Fonts
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=10, family="Segoe UI")

        # Grid weights
        self._root.grid_rowconfigure(1, weight=1)
        self._root.grid_columnconfigure(0, weight=1)

        # ── Build sections ──
        self._build_title_bar()
        self._build_header()
        self._build_log_area()
        self._build_input_area()
        self._build_toggle_bar()
        self._build_action_bar()

        # Start hidden
        self._root.withdraw()

        # Start queue polling + status animation
        self._poll_queues()
        self._animate_status()

        self._root.mainloop()

    # ── Title Bar ────────────────────────────────────────────────

    def _build_title_bar(self) -> None:
        """Custom draggable title bar."""
        frame = tk.Frame(self._root, bg=TITLE_BG, height=36, cursor="fleur")
        frame.grid(row=0, column=0, sticky="ew")
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, weight=1)

        # Make dragable
        frame.bind("<Button-1>", self._start_drag)
        frame.bind("<B1-Motion>", self._do_drag)
        frame.bind("<ButtonRelease-1>", self._stop_drag)

        # Title text
        title = tk.Label(frame, text="AILIEN", font=("Segoe UI", 11, "bold"),
                         fg=FG_ACCENT, bg=TITLE_BG, cursor="fleur")
        title.grid(row=0, column=0, padx=(14, 0), pady=0, sticky="w")
        title.bind("<Button-1>", self._start_drag)
        title.bind("<B1-Motion>", self._do_drag)

        # Window controls
        btn_frame = tk.Frame(frame, bg=TITLE_BG)
        btn_frame.grid(row=0, column=1, padx=(0, 8), sticky="e")

        for symbol, cmd, hover in [
            ("─", self.hide, FG_SECONDARY),
            ("✕", self.close, FG_RED),
        ]:
            lbl = tk.Label(btn_frame, text=symbol, font=("Segoe UI", 12),
                           fg=FG_SECONDARY, bg=TITLE_BG, cursor="hand2",
                           padx=8, pady=2)
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, c=cmd: c())
            lbl.bind("<Enter>", lambda e, l=lbl, h=hover: l.configure(fg=h))
            lbl.bind("<Leave>", lambda e, l=lbl: l.configure(fg=FG_SECONDARY))

    def _start_drag(self, event):
        self._drag_data["x"] = event.x_root - self._root.winfo_x()
        self._drag_data["y"] = event.y_root - self._root.winfo_y()

    def _do_drag(self, event):
        x = event.x_root - self._drag_data["x"]
        y = event.y_root - self._drag_data["y"]
        self._root.geometry(f"+{x}+{y}")

    def _stop_drag(self, event):
        pass

    # ── Header ───────────────────────────────────────────────────

    def _build_header(self) -> None:
        """Status bar with indicator dot, label, listen + stop buttons."""
        frame = tk.Frame(self._root, bg=BG_DARK, height=56)
        frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(10, 4))
        frame.grid_propagate(False)
        frame.grid_columnconfigure(2, weight=1)

        # Status indicator (animated dot)
        self._indicator_canvas = tk.Canvas(frame, width=28, height=28,
                                           bg=BG_DARK, highlightthickness=0)
        self._indicator_canvas.grid(row=0, column=0, padx=(0, 10))
        self._indicator_dot = self._indicator_canvas.create_oval(
            4, 4, 24, 24, fill=STATUS_COLORS["idle"], outline=""
        )
        # Glow effect behind dot
        self._indicator_canvas.create_oval(
            2, 2, 26, 26, fill="", outline=STATUS_COLORS["idle"], width=2
        )

        self._status_label = tk.Label(frame, text=STATUS_LABELS["idle"],
                                      font=("Segoe UI", 13, "bold"),
                                      fg=FG_PRIMARY, bg=BG_DARK)
        self._status_label.grid(row=0, column=1, sticky="w")

        # Listen button (canvas for custom look)
        self._listen_btn = tk.Canvas(frame, width=100, height=36,
                                     bg=BG_DARK, highlightthickness=0,
                                     cursor="hand2")
        self._listen_btn.grid(row=0, column=3, padx=(0, 6))
        self._draw_listen_btn(False)
        self._listen_btn.bind("<Button-1>", lambda e: self._toggle_voice())

        # Stop button
        self._stop_btn = tk.Button(frame, text="⏹", font=("Segoe UI", 16),
                                   fg=FG_RED, bg=BG_LIGHT,
                                   activebackground="#3d1a1a",
                                   activeforeground=FG_RED,
                                   relief="flat", bd=0, cursor="hand2",
                                   padx=12, pady=4,
                                   state="disabled",
                                   command=self._on_stop)
        self._stop_btn.grid(row=0, column=4)

    def _draw_listen_btn(self, active: bool) -> None:
        """Redraw the listen/pause button."""
        self._listen_btn.delete("all")
        w, h = 100, 36
        r = 18
        if active:
            # PAUSE — yellow background
            self._listen_btn.create_rounded_rect(0, 0, w, h, r,
                                                 fill="#3d3520", outline=FG_YELLOW, width=1)
            self._listen_btn.create_text(w//2, h//2, text="⏸  PAUSE",
                                         fill=FG_YELLOW,
                                         font=("Segoe UI", 10, "bold"))
        else:
            # LISTEN — green background
            self._listen_btn.create_rounded_rect(0, 0, w, h, r,
                                                 fill="#1a3d2a", outline=FG_GREEN, width=1)
            self._listen_btn.create_text(w//2, h//2, text="🎤  LISTEN",
                                         fill=FG_GREEN,
                                         font=("Segoe UI", 10, "bold"))

    # ── Chat Log ─────────────────────────────────────────────────

    def _build_log_area(self) -> None:
        """Scrollable chat log with message bubbles."""
        container = tk.Frame(self._root, bg=BG_DARK)
        container.grid(row=2, column=0, sticky="nsew", padx=16, pady=4)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Canvas for scrolling
        self._log_canvas = tk.Canvas(container, bg=BG_MEDIUM,
                                     highlightthickness=0, bd=0)
        self._log_canvas.grid(row=0, column=0, sticky="nsew")

        # Scrollbar
        scrollbar = tk.Scrollbar(container, orient="vertical",
                                 command=self._log_canvas.yview,
                                 bg=BG_LIGHT, troughcolor=BG_DARK)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._log_canvas.configure(yscrollcommand=scrollbar.set)

        # Inner frame for messages
        self._log_inner = tk.Frame(self._log_canvas, bg=BG_MEDIUM)
        self._log_window = self._log_canvas.create_window(
            (0, 0), window=self._log_inner, anchor="nw", width=self._log_canvas.winfo_width()
        )

        # Bind resize
        self._log_inner.bind("<Configure>", self._on_log_configure)
        self._log_canvas.bind("<Configure>", self._on_canvas_configure)

        # Bind mousewheel
        self._log_canvas.bind("<Enter>", self._bind_mousewheel)
        self._log_canvas.bind("<Leave>", self._unbind_mousewheel)

    def _on_log_configure(self, event):
        self._log_canvas.configure(scrollregion=self._log_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._log_canvas.itemconfig(self._log_window, width=event.width)

    def _bind_mousewheel(self, event):
        self._log_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        self._log_canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self._log_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _add_bubble(self, text: str, is_user: bool) -> None:
        """Add a chat bubble to the log."""
        if not self._log_inner:
            return

        bubble = tk.Frame(self._log_inner, bg=BG_MEDIUM)
        bubble.pack(fill="x", padx=8, pady=(0, 2))

        # Bg color
        bg = BG_BUBBLE_USER if is_user else BG_BUBBLE_AI
        fg = "#ffffff" if is_user else FG_PRIMARY
        justify = "right" if is_user else "left"
        anchor = "e" if is_user else "w"

        # Label name
        name = tk.Label(bubble, text="You" if is_user else "AILIEN",
                        font=("Segoe UI", 8, "bold"),
                        fg=FG_ACCENT if is_user else FG_GREEN,
                        bg=BG_MEDIUM)
        name.pack(anchor=anchor, padx=4, pady=(4, 0))

        # Message bubble
        msg_frame = tk.Frame(bubble, bg=bg, bd=0)
        msg_frame.pack(anchor=anchor, padx=4, pady=(1, 4))

        msg = tk.Label(msg_frame, text=text,
                       font=("Segoe UI", 10),
                       fg=fg, bg=bg, wraplength=380,
                       justify=justify, anchor=anchor)
        msg.pack(padx=12, pady=8)

        # Rounded corners via padding
        def _rounded_rect(canvas, x1, y1, x2, y2, r=12, **kwargs):
            points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
                      x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
                      x1, y2, x1, y2-r, x1, y1+r, x1, y1]
            return canvas.create_polygon(points, **kwargs, smooth=True)

        # Auto-scroll to bottom
        if self._log_canvas:
            self._log_canvas.yview_moveto(1.0)

    def _add_divider(self, text: str) -> None:
        """Add a system divider."""
        if not self._log_inner:
            return

        frame = tk.Frame(self._log_inner, bg=BG_MEDIUM)
        frame.pack(fill="x", padx=8, pady=2)

        lbl = tk.Label(frame, text=f"── {text} ──",
                       font=("Segoe UI", 8, "italic"),
                       fg=FG_SECONDARY, bg=BG_MEDIUM)
        lbl.pack()

    def _add_error(self, text: str) -> None:
        """Add an error message."""
        if not self._log_inner:
            return

        frame = tk.Frame(self._log_inner, bg=BG_MEDIUM)
        frame.pack(fill="x", padx=8, pady=2)

        lbl = tk.Label(frame, text=f"⚠ {text}",
                       font=("Segoe UI", 9),
                       fg=FG_RED, bg=BG_MEDIUM)
        lbl.pack(anchor="w", padx=4, pady=4)

    # ── Input Area ───────────────────────────────────────────────

    def _build_input_area(self) -> None:
        """Text input with send button."""
        frame = tk.Frame(self._root, bg=BG_DARK, height=52)
        frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 6))
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, weight=1)

        # Entry with rounded border look
        entry_frame = tk.Frame(frame, bg=BORDER_COLOR, bd=1)
        entry_frame.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        entry_frame.grid_columnconfigure(0, weight=1)
        entry_frame.grid_rowconfigure(0, weight=1)

        self._input_entry = tk.Text(entry_frame, height=1, wrap="word",
                                     font=("Segoe UI", 11),
                                     bg=BG_INPUT, fg=FG_PRIMARY,
                                     insertbackground=FG_ACCENT,
                                     relief="flat", bd=0,
                                     padx=12, pady=10)
        self._input_entry.grid(row=0, column=0, sticky="ew")
        self._input_entry.bind("<Return>", self._on_send)
        self._input_entry.bind("<Shift-Return>", lambda e: None)

        # Send button (canvas)
        self._send_btn = tk.Canvas(frame, width=48, height=36,
                                   bg=BG_DARK, highlightthickness=0,
                                   cursor="hand2")
        self._send_btn.grid(row=0, column=1)
        self._send_btn.create_rounded_rect(0, 0, 48, 36, 18,
                                           fill="#1a3d2a", outline=FG_GREEN, width=1)
        self._send_btn.create_text(24, 18, text="→", fill=FG_GREEN,
                                   font=("Segoe UI", 16, "bold"))
        self._send_btn.bind("<Button-1>", self._on_send)

    # ── Toggle Bar ───────────────────────────────────────────────

    def _build_toggle_bar(self) -> None:
        """Toggle switches for settings."""
        frame = tk.Frame(self._root, bg=BG_DARK)
        frame.grid(row=4, column=0, sticky="ew", padx=16, pady=(2, 4))

        self._voice_var = tk.BooleanVar(value=config.AGENT_VOICE_FEEDBACK)
        self._proactive_var = tk.BooleanVar(value=config.JARVIS_PROACTIVE)
        self._confirm_var = tk.BooleanVar(value=config.AGENT_CONFIRM_DANGEROUS)

        for label, var, attr in [
            ("Voice", self._voice_var, "AGENT_VOICE_FEEDBACK"),
            ("Monitor", self._proactive_var, "JARVIS_PROACTIVE"),
            ("Confirm", self._confirm_var, "AGENT_CONFIRM_DANGEROUS"),
        ]:
            cell = tk.Frame(frame, bg=BG_DARK)
            cell.pack(side="left", padx=(0, 14))

            lbl = tk.Label(cell, text=label, font=("Segoe UI", 9),
                           fg=FG_SECONDARY, bg=BG_DARK)
            lbl.pack(side="left", padx=(0, 4))

            self._make_toggle(cell, var, attr)

    def _make_toggle(self, parent, var, config_attr: str):
        """Draw a toggle switch that updates the given config attribute."""
        canvas = tk.Canvas(parent, width=32, height=18,
                           bg=BG_DARK, highlightthickness=0,
                           cursor="hand2")
        canvas.pack(side="left")

        def _redraw():
            canvas.delete("all")
            on = var.get()
            bg = "#3fb950" if on else "#30363d"
            knob_x = 16 if on else 4
            canvas.create_oval(0, 0, 32, 18, fill=bg, outline="")
            canvas.create_oval(knob_x, 2, knob_x + 14, 16,
                               fill="#ffffff", outline="")

        def _click(e):
            var.set(not var.get())
            setattr(config, config_attr, var.get())
            _redraw()

        canvas.bind("<Button-1>", _click)
        _redraw()
        return canvas

    # ── Action Bar ───────────────────────────────────────────────

    def _build_action_bar(self) -> None:
        """Quick action buttons."""
        frame = tk.Frame(self._root, bg=BG_DARK, height=44)
        frame.grid(row=5, column=0, sticky="ew", padx=16, pady=(2, 12))
        frame.grid_propagate(False)

        actions = [
            ("📷  Screenshot", self._on_screenshot),
            ("📁  Notes", self._on_open_knowledge),
            ("📋  Log", self._on_open_log),
            ("🗑  Clear", self._on_clear),
        ]

        for text, cmd in actions:
            btn = tk.Button(frame, text=text, command=cmd,
                            font=("Segoe UI", 9),
                            fg=FG_PRIMARY, bg=BG_LIGHT,
                            activebackground=BG_INPUT,
                            activeforeground=FG_PRIMARY,
                            relief="flat", bd=0, cursor="hand2",
                            padx=8, pady=5)
            btn.pack(side="left", padx=(0, 6))
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=BG_INPUT))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=BG_LIGHT))

    # ── Callbacks ────────────────────────────────────────────────

    def _toggle_voice(self) -> None:
        with self._voice_lock:
            self._voice_active = not self._voice_active
            active = self._voice_active
        self._draw_listen_btn(active)
        label = "Voice listening active." if active else "Voice listening paused."
        self.append_message("system", label)
        if self._voice_toggle_callback:
            self._voice_toggle_callback(active)

    def _on_stop(self) -> None:
        if self._stop_callback:
            self._stop_callback()
        self.put_status("idle")
        self._stop_btn.config(state="disabled")

    def _on_send(self, event=None) -> None:
        if not self._input_entry:
            return "break"
        text = self._input_entry.get("1.0", tk.END).strip()
        if not text:
            return "break"
        self._input_entry.delete("1.0", tk.END)
        self._submit_command(text)
        return "break"  # prevent newline from Return key

    def _submit_command(self, text: str) -> None:
        self.append_message("user", text)
        self._stop_btn.config(state="normal")
        self.put_status("thinking")
        if self._input_callback:
            self._input_callback(text)

    def _on_screenshot(self) -> None:
        self._submit_command("Take a screenshot and describe what you see")

    def _on_open_knowledge(self) -> None:
        try:
            knowledge_dir = config.PROJECT_DIR / "knowledge"
            knowledge_dir.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["xdg-open", str(knowledge_dir)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            logger.warning("Could not open knowledge folder: %s", exc)

    def _on_open_log(self) -> None:
        try:
            subprocess.Popen(["xdg-open", str(config.LOG_FILE.resolve())],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            logger.warning("Could not open log file: %s", exc)

    def _on_clear(self) -> None:
        if self._log_inner:
            for w in self._log_inner.winfo_children():
                w.destroy()

    # ── Queue Polling ────────────────────────────────────────────

    def _poll_queues(self) -> None:
        if self._root is None:
            return
        try:
            while True:
                status = self._status_queue.get_nowait()
                self._update_status(status)
        except Empty:
            pass
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
        if status == "_voice_on":
            self._draw_listen_btn(True)
            return
        if status == "_voice_off":
            self._draw_listen_btn(False)
            return

        self._status = status
        color = STATUS_COLORS.get(status, STATUS_COLORS["idle"])
        text = STATUS_LABELS.get(status, status.capitalize())

        if self._indicator_canvas and self._indicator_dot is not None:
            try:
                self._indicator_canvas.itemconfig(self._indicator_dot, fill=color)
            except Exception:
                pass
        if self._status_label:
            try:
                self._status_label.config(text=text)
            except Exception:
                pass

        if status in ("thinking", "speaking", "listening"):
            self._stop_btn.config(state="normal")
        else:
            self._stop_btn.config(state="disabled")

        if self._root:
            try:
                self._root.title(f"AILIEN — {text}")
            except Exception:
                pass

    def _append_to_log(self, role: str, text: str) -> None:
        if role == "user":
            self._add_bubble(text, True)
        elif role == "agent":
            self._add_bubble(text, False)
        elif role == "system":
            self._add_divider(text)
        elif role == "error":
            self._add_error(text)
        else:
            self._add_divider(text)

    # ── Animated Status Indicator ────────────────────────────────

    def _animate_status(self) -> None:
        """Subtle pulsing glow animation on the status dot."""
        if self._root is None:
            return
        try:
            color = STATUS_COLORS.get(self._status, "#8b949e")
            t = time.time()
            # Gentle pulse: alpha between 0.3 and 1.0
            pulse = 0.3 + 0.7 * abs(((t * 2) % 2) - 1)
            if self._indicator_canvas and self._indicator_dot is not None:
                try:
                    self._indicator_canvas.itemconfig(self._indicator_dot,
                                                      fill=color, stipple="" )
                except Exception:
                    pass
        except Exception:
            pass
        if self._root:
            try:
                self._anim_after_id = self._root.after(50, self._animate_status)
            except Exception:
                pass


# ── Patch Canvas with rounded rect support ────────────────────
def _create_rounded_rect(self, x1, y1, x2, y2, r=12, **kwargs):
    points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
              x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
              x1, y2, x1, y2-r, x1, y1+r, x1, y1]
    return self.create_polygon(points, **kwargs, smooth=True)

tk.Canvas.create_rounded_rect = _create_rounded_rect
