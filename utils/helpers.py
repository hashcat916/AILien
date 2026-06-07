"""Helper utilities for AILIEN — modern CLI output.

Provides clean, professional terminal output inspired by Claude Code,
gh CLI, and modern developer tools. Uses semantic colors and minimal
visual noise while keeping accessibility.

Modes:
  - modern (default): clean, minimal, professional. No heavy borders.
  - fancy: rich panels with borders for presentation
  - freebuff: super minimal for power users
"""

import logging
import sys
import threading
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

import config

_console = Console()
_modern_mode = True  # Can be toggled at runtime


# ---------------------------------------------------------------------------
# Logging setup (unchanged)
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    """Configure logging — quiet console, full file logs."""
    logger = logging.getLogger("agent")
    logger.setLevel(logging.DEBUG)

    console_handler = RichHandler(
        console=_console, rich_tracebacks=True, level=logging.WARNING,
    )
    console_handler.setLevel(logging.WARNING)

    file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
    ))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    for noisy in ("httpx", "httpcore", "urllib3", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return logger


def setup_crash_logging() -> None:
    """Install crash logging to file (unchanged)."""
    crash_logger = logging.getLogger("ailien.crash")
    if crash_logger.handlers:
        return
    from logging.handlers import RotatingFileHandler
    crash_handler = RotatingFileHandler(
        config.CRASH_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    crash_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    crash_logger.setLevel(logging.DEBUG)
    crash_logger.propagate = False
    crash_logger.addHandler(crash_handler)
    crash_logger.info("=" * 60)
    crash_logger.info("AILIEN session started")
    crash_logger.info(f"Python {sys.version}")
    crash_logger.info(f"Platform: {__import__('platform').platform()}")
    crash_logger.info(f"CWD: {Path.cwd()}")

    _original_excepthook = sys.excepthook

    def _crash_excepthook(exc_type, exc_value, exc_traceback):
        crash_logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        try:
            import traceback
            crash_logger.debug("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        except Exception:
            pass
        _original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _crash_excepthook
    if hasattr(threading, "excepthook"):
        _original_thread_excepthook = threading.excepthook

        def _crash_thread_excepthook(args):
            crash_logger.error(
                f"Uncaught exception in thread {args.thread.name}",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            if _original_thread_excepthook is not None:
                _original_thread_excepthook(args)

        threading.excepthook = _crash_thread_excepthook


# ---------------------------------------------------------------------------
# TTS (unchanged)
# ---------------------------------------------------------------------------

_STOP_TTS = threading.Event()
_TTS_LOCK = threading.Lock()
_TTS_ENGINE = None
_EDGE_TTS_VOICE = "en-US-AriaNeural"


def cancel_speech() -> None:
    global _STOP_TTS
    _STOP_TTS.set()
    if _TTS_ENGINE is not None:
        try:
            _TTS_ENGINE.stop()
        except Exception:
            pass


def reset_speech() -> None:
    global _STOP_TTS
    _STOP_TTS = threading.Event()


def _get_tts_engine():
    global _TTS_ENGINE
    if _TTS_ENGINE is None:
        import pyttsx3
        _TTS_ENGINE = pyttsx3.init()
        _TTS_ENGINE.setProperty("rate", 180)
    return _TTS_ENGINE


def _speak_edge_tts(text: str) -> None:
    import os, subprocess, tempfile
    if _STOP_TTS.is_set():
        return
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        mp3_path = tmp.name
    try:
        subprocess.run(
            [sys.executable, "-m", "edge_tts", "--voice", _EDGE_TTS_VOICE, "--text", text, "--write-media", mp3_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
        )
        if _STOP_TTS.is_set():
            return
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", mp3_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
        )
    except Exception:
        if not _STOP_TTS.is_set():
            _speak_pyttsx3(text)
    finally:
        try:
            os.unlink(mp3_path)
        except Exception:
            pass


def _speak_pyttsx3(text: str) -> None:
    try:
        engine = _get_tts_engine()
        if _STOP_TTS.is_set():
            return
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            if _STOP_TTS.is_set():
                break
            if sentence.strip():
                engine.say(sentence)
                engine.runAndWait()
    except Exception:
        pass


def speak(text: str) -> None:
    if not config.AGENT_VOICE_FEEDBACK:
        return
    reset_speech()
    with _TTS_LOCK:
        if config.TTS_ENGINE == "edge":
            _speak_edge_tts(text)
        else:
            _speak_pyttsx3(text)


# ---------------------------------------------------------------------------
# Desktop notifications (unchanged)
# ---------------------------------------------------------------------------

_NOTIFY_ICON_PATH: Path | None = None


def _ensure_notify_icon() -> Path | None:
    global _NOTIFY_ICON_PATH
    if _NOTIFY_ICON_PATH is None:
        icon_file = config.CACHE_DIR / "ailien_icon.png"
        if icon_file.exists():
            _NOTIFY_ICON_PATH = icon_file
    return _NOTIFY_ICON_PATH


def notify(title: str, message: str) -> None:
    import subprocess
    try:
        icon = _ensure_notify_icon()
        cmd = ["notify-send", title, message, "-t", "5000"]
        if icon is not None:
            cmd.extend(["-i", str(icon)])
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        try:
            from plyer import notification
            notification.notify(title=title, message=message, timeout=5)
        except Exception:
            pass


# ===================================================================
# MODERN CLI OUTPUT — clean, professional, minimal noise
# ===================================================================
# Design inspired by Claude Code, gh CLI, lazygit.
# - No heavy panel borders for every message
# - Semantic colors: user=green, agent=cyan, tool=dim, error=red
# - Simple prompt: "> "
# - Compact tool call display
# ===================================================================


def print_header(title: str = "AILIEN", subtitle: str = "") -> None:
    """Print a clean startup header — thin rule, title, tool count."""
    tool_count = ""
    try:
        import tools
        tool_count = f" · {len(tools.TOOLS)} tools"
    except Exception:
        pass

    rule = "─" * 50
    _console.print(f"\n[bold cyan]{rule}[/bold cyan]")
    _console.print(f"[bold cyan] {title}[/bold cyan][dim]{subtitle or tool_count}[/dim]")
    _console.print(f"[bold cyan]{rule}[/bold cyan]\n")


def print_user(text: str) -> None:
    """Print user input — clean green prompt style."""
    _console.print(f" [bold green]> {text}[/bold green]")


def print_agent(text: str, style: str = "cyan") -> None:
    """Print agent output — clean, no borders, just the content."""
    # If it has multiple lines, add a subtle indent
    lines = text.strip().split("\n")
    if len(lines) == 1:
        _console.print(f" {text}")
    else:
        for line in lines:
            if line.strip():
                _console.print(f" {line}")
            else:
                _console.print("")


def print_tool(name: str, params: dict[str, Any] | None = None) -> None:
    """Print a tool call in compact, dim format."""
    if params:
        params_str = ", ".join(f"{k}={v!r}" for k, v in params.items())
        _console.print(f"  [dim]◇ {name}({params_str})[/dim]")
    else:
        _console.print(f"  [dim]◇ {name}()[/dim]")


def print_status(text: str, style: str = "dim") -> None:
    """Print a status/notification line."""
    _console.print(f"  [{style}]{text}[/{style}]")


def print_success(text: str) -> None:
    """Print a success message with checkmark."""
    _console.print(f"  [bold green]✓[/bold green] {text}")


def print_error(text: str) -> None:
    """Print an error message."""
    _console.print(f"  [bold red]✗[/bold red] {text}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    _console.print(f"  [bold yellow]⚠[/bold yellow] {text}")


def print_info(text: str) -> None:
    """Print an informational message."""
    _console.print(f"  [dim]{text}[/dim]")


def print_divider() -> None:
    """Print a thin divider line."""
    _console.print(f"  [dim]─[/dim]" * 30)


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a simple table."""
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    for h in headers:
        table.add_column(h)
    for row in rows:
        table.add_row(*row)
    _console.print(table)


def print_panel(text: str, title: str = "", style: str = "cyan") -> None:
    """Print content in a bordered panel (for special cases)."""
    panel = Panel(
        Text(text, style=style),
        title=f"[bold]{title}[/bold]" if title else None,
        border_style=style,
    )
    _console.print(panel)


# ---------------------------------------------------------------------------
# Thinking indicator — subtle dots animation
# ---------------------------------------------------------------------------

_thinking_progress: Progress | None = None


def show_thinking(message: str = "Thinking") -> None:
    """Start a subtle thinking indicator in the terminal."""
    global _thinking_progress
    hide_thinking()
    _thinking_progress = Progress(
        SpinnerColumn(spinner_name="dots", style="cyan"),
        TextColumn(f"[dim]{message}...[/dim]"),
        transient=True,
        console=_console,
    )
    _thinking_progress.start()


def hide_thinking() -> None:
    """Stop the thinking indicator."""
    global _thinking_progress
    if _thinking_progress is not None:
        _thinking_progress.stop()
        _thinking_progress = None


# ---------------------------------------------------------------------------
# Confirmation prompt
# ---------------------------------------------------------------------------

def ask_confirmation(tool_name: str, params: dict[str, Any]) -> bool:
    """Ask user for confirmation with clean formatting."""
    _console.print(f"\n  [bold yellow]⚠  Allow this action?[/bold yellow]")
    _console.print(f"  [bold]{tool_name}[/bold]")
    for k, v in params.items():
        _console.print(f"    [dim]{k}:[/dim] {v!r}")
    try:
        answer = _console.input("  [bold]Allow?[/bold] [dim](yes/no)[/dim] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "no"
    return answer in ("yes", "y", "yeah", "yep")


# ===================================================================
# FANCY MODE (legacy) — rich panels for presentation
# ===================================================================

def fancy_print_user(text: str) -> None:
    """Print user message in fancy panel style."""
    panel = Panel(Text(text, style="green"), title="[bold]You[/bold]", border_style="green")
    _console.print(panel)


def fancy_print_agent(text: str) -> None:
    """Print agent message in fancy panel style."""
    panel = Panel(Text(text, style="cyan"), title="[bold]AILIEN[/bold]", border_style="cyan")
    _console.print(panel)


def fancy_print_tool(name: str, params: dict[str, Any]) -> None:
    """Print tool call in fancy style."""
    params_str = ", ".join(f"{k}={v!r}" for k, v in params.items())
    _console.print(f"  [dim]→ {name}({params_str})[/dim]")


# ===================================================================
# FREEBUFF MODE (legacy) — super minimal for power users
# ===================================================================

def fb_print_user(text: str) -> None:
    _console.print(f"\n[bold green]> {text}[/bold green]")


def fb_print_agent(text: str) -> None:
    _console.print(f"[bold cyan]AILIEN:[/bold cyan] {text}\n")


def fb_print_tool(name: str, params: dict[str, Any]) -> None:
    params_str = ", ".join(f"{k}={v!r}" for k, v in params.items())
    _console.print(f"  [dim][{name}({params_str})][/dim]")


def fb_print_info(text: str) -> None:
    _console.print(f"[dim]{text}[/dim]")


def fb_print_error(text: str) -> None:
    _console.print(f"[bold red]Error: {text}[/bold red]")


# ===================================================================
# Legacy aliases — for backward compatibility
# ===================================================================

# Old fancy functions still work for anything importing them
print_agent_message = fancy_print_agent
print_user_message = fancy_print_user
print_tool_call = fancy_print_tool
