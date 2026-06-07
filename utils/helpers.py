"""Helper utilities for AILIEN."""
import logging
import sys
import threading
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.text import Text

import config

_console = Console()


def setup_logging() -> logging.Logger:
    """Configure logging with rich formatting."""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(console=_console, rich_tracebacks=True),
            logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        ],
    )
    return logging.getLogger("agent")


def setup_crash_logging() -> None:
    """Install a sys.excepthook that writes uncaught exceptions to a dedicated crash log.

    The crash log includes full tracebacks, timestamps, and system context so we can
    diagnose what caused a hard crash even if the terminal was destroyed.
    """
    crash_logger = logging.getLogger("ailien.crash")
    if crash_logger.handlers:
        return  # Already configured; prevent duplicate handlers

    from logging.handlers import RotatingFileHandler

    crash_handler = RotatingFileHandler(
        config.CRASH_LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    crash_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    crash_logger.setLevel(logging.DEBUG)
    crash_logger.propagate = False
    crash_logger.addHandler(crash_handler)

    # Log separator so each run is easy to spot
    crash_logger.info("=" * 60)
    crash_logger.info("AILIEN session started")
    crash_logger.info(f"Python {sys.version}")
    crash_logger.info(f"Platform: {__import__('platform').platform()}")
    crash_logger.info(f"CWD: {Path.cwd()}")

    _original_excepthook = sys.excepthook

    def _crash_excepthook(exc_type, exc_value, exc_traceback):
        """Log uncaught exceptions to the crash file, then call the original hook."""
        crash_logger.error(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        # Extra context that may help debugging
        try:
            import traceback
            tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            crash_logger.debug(f"Full traceback:\n{tb_str}")
        except Exception:
            pass
        try:
            import platform
            crash_logger.debug(f"Processor: {platform.processor()}")
            crash_logger.debug(f"Machine: {platform.machine()}")
        except Exception:
            pass
        _original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _crash_excepthook

    # Also catch exceptions in background threads (Python 3.8+)
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


# Cached TTS engines
_TTS_ENGINE = None
_EDGE_TTS_VOICE = "en-US-AriaNeural"


def _get_tts_engine():
    """Lazy-load and cache the pyttsx3 engine."""
    global _TTS_ENGINE
    if _TTS_ENGINE is None:
        import pyttsx3
        _TTS_ENGINE = pyttsx3.init()
        _TTS_ENGINE.setProperty("rate", 180)
    return _TTS_ENGINE


def _speak_edge_tts(text: str) -> None:
    """Speak using edge-tts (natural-sounding voice) via temp MP3 + ffplay."""
    import os
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        mp3_path = tmp.name

    try:
        # Generate speech
        subprocess.run(
            [sys.executable, "-m", "edge_tts", "--voice", _EDGE_TTS_VOICE, "--text", text, "--write-media", mp3_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        # Play it
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", mp3_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except Exception:
        # Fallback to pyttsx3 if edge-tts fails
        _speak_pyttsx3(text)
    finally:
        try:
            os.unlink(mp3_path)
        except Exception:
            pass


def _speak_pyttsx3(text: str) -> None:
    """Speak using the offline pyttsx3 engine (robotic voice)."""
    try:
        engine = _get_tts_engine()
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass


def speak(text: str) -> None:
    """Text-to-speech feedback. Routes to the configured engine."""
    if not config.AGENT_VOICE_FEEDBACK:
        return
    if config.TTS_ENGINE == "edge":
        _speak_edge_tts(text)
    else:
        _speak_pyttsx3(text)


_NOTIFY_ICON_PATH: Path | None = None


def _ensure_notify_icon() -> Path | None:
    """Return the path to the downloaded alien icon for notifications."""
    global _NOTIFY_ICON_PATH
    if _NOTIFY_ICON_PATH is None:
        icon_file = config.CACHE_DIR / "ailien_icon.png"
        if icon_file.exists():
            _NOTIFY_ICON_PATH = icon_file
    return _NOTIFY_ICON_PATH


def notify(title: str, message: str) -> None:
    """Desktop notification via notify-send with the AILIEN emoji icon."""
    import subprocess
    try:
        icon = _ensure_notify_icon()
        cmd = ["notify-send", title, message, "-t", "5000"]
        if icon is not None:
            cmd.extend(["-i", str(icon)])
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except Exception:
        # Fallback to plyer
        try:
            from plyer import notification as plyer_notify
            plyer_notify.notify(title=title, message=message, timeout=5)
        except Exception:
            pass


def print_agent_message(text: str, style: str = "cyan") -> None:
    """Print a styled agent message."""
    panel = Panel(Text(text, style=style), title="[bold]Agent[/bold]", border_style=style)
    _console.print(panel)


def print_user_message(text: str) -> None:
    """Print a styled user message."""
    panel = Panel(Text(text, style="green"), title="[bold]You[/bold]", border_style="green")
    _console.print(panel)


def print_tool_call(name: str, params: dict[str, Any]) -> None:
    """Print a tool call for transparency."""
    params_str = ", ".join(f"{k}={v!r}" for k, v in params.items())
    _console.print(f"[dim]  → {name}({params_str})[/dim]")


def print_error(text: str) -> None:
    """Print an error message."""
    _console.print(f"[bold red]Error:[/bold red] {text}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    _console.print(f"[bold yellow]Warning:[/bold yellow] {text}")


# ---------------------------------------------------------------------------
# Freebuff (minimal inline) helpers — no panels, just plain terminal text
# ---------------------------------------------------------------------------

def fb_print_user(text: str) -> None:
    """Print a user message in freebuff inline style."""
    _console.print(f"\n[bold green]> {text}[/bold green]")


def fb_print_agent(text: str) -> None:
    """Print an agent message in freebuff inline style."""
    _console.print(f"[bold cyan]AILIEN:[/bold cyan] {text}\n")


def fb_print_tool(name: str, params: dict[str, Any]) -> None:
    """Print a tool call in freebuff inline style."""
    params_str = ", ".join(f"{k}={v!r}" for k, v in params.items())
    _console.print(f"[dim]  [{name}({params_str})][/dim]")


def fb_print_info(text: str) -> None:
    """Print an info line in freebuff inline style."""
    _console.print(f"[dim]{text}[/dim]")


def fb_print_error(text: str) -> None:
    """Print an error in freebuff inline style."""
    _console.print(f"[bold red]Error: {text}[/bold red]")
