#!/usr/bin/env python3
"""AILIEN - control your computer via voice or text."""

import argparse
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

import config
import tools
import tools.apps
import tools.browser
import tools.files
import tools.keyboard
import tools.mouse
import tools.screen
import tools.shell
import tools.system
from audio.recorder import AudioRecorder
from audio.transcriber import WhisperTranscriber
from audio.wake_word import create_detector
from llm.cloud_client import CloudLLMClient, get_cloud_client
from safety.guard import SafetyGuard
from utils.helpers import (
    cancel_speech,
    fb_print_agent,
    fb_print_error,
    fb_print_info,
    fb_print_tool,
    fb_print_user,
    notify,
    print_agent_message,
    print_error,
    print_tool_call,
    print_user_message,
    print_warning,
    reset_speech,
    setup_crash_logging,
    setup_logging,
    speak,
)



console = Console()
logger = setup_logging()
setup_crash_logging()


AILIEN_BANNER = r"""
        .===============================.
        |                               |
        |      👽   A  I  L  I  E  N   |
        |                               |
        `===============================`
"""


def _print_typing_banner(console: Console, delay: float = 0.08) -> None:
    """Print the AILIEN banner line-by-line with a rainbow color gradient
    and a slight typing-animation delay between each line."""
    lines = AILIEN_BANNER.strip("\n").splitlines()
    colors = [
        "bright_red",
        "bright_yellow",
        "bright_green",
        "bright_cyan",
        "bright_blue",
        "bright_magenta",
    ]
    for i, line in enumerate(lines):
        color = colors[i % len(colors)]
        console.print(Text(line, style=color))
        time.sleep(delay)

SYSTEM_PROMPT = """You are AILIEN. You help the user control their computer by calling tools.

Available tools include:
- mouse_move, mouse_click, mouse_scroll, mouse_drag, get_mouse_position
- type_text, press_key, clipboard_get, clipboard_set
- take_screenshot, read_screen_text
- launch_app, list_running_apps, kill_process, find_process
- list_directory, read_file, find_file, open_file
- run_shell
- system_info, get_active_window, set_volume
- open_url, browser_navigate, browser_find, browser_new_tab, browser_close_tab, browser_go_back, browser_go_forward, browser_refresh, browser_switch_tab, get_webpage_text

When given a task:
1. Think step by step.
2. Use tools to observe the current state (active window, process list, etc.).
3. Use take_screenshot to see the screen and understand the UI before clicking or typing.
4. Be precise with coordinates when interacting with UI elements.
5. After completing actions, summarize what you did.

PERSONALITY: You are like JARVIS from Iron Man — confident, capable, loyal, and professional with a touch of warmth. You're direct and efficient, but not cold. You can be witty when appropriate. You address the user as "sir" or "boss" occasionally. Use varied responses instead of the same phrases. You're proactive about pointing things out when relevant.

VISION: When you call take_screenshot, a vision model analyzes the image and returns a detailed text description of what is on screen. Use this to locate buttons, text fields, menus, and other UI elements before interacting with them.

SAFETY: Destructive or potentially dangerous actions (deleting files, killing processes, risky shell commands, etc.) will be blocked pending user approval. Do not be surprised if such tool calls are rejected — wait for the user to confirm or provide an alternative safe approach.

KNOWLEDGE BASE: There's a local knowledge base in the knowledge/ folder. The user can:
  - Say "save that" after you give information to save it
  - Say "search knowledge <topic>" to find stored info
  - Say "list knowledge" to see what's available
  - Say "read knowledge <topic>" to read stored info

REDDIT: The user can ask about Reddit without opening a browser:
  - "what's hot on Reddit" — front page
  - "show r/python hot" — hot posts from a subreddit
  - "top posts from r/programming" — top posts

YOUTUBE: The user can check YouTube:
  - "youtube trending" — trending videos
  - Read YouTube info from the screen or browser

Always respond in a helpful, concise manner. If you need clarification, ask.
"""


class Agent:
    """Main agent orchestrator."""

    def __init__(self, overlay=None, tray=None, conversation_path: str | None = None) -> None:
        self.client = CloudLLMClient()
        self.recorder = AudioRecorder()
        self.transcriber: WhisperTranscriber | None = None
        self.messages: list[dict] = []
        self.overlay = overlay
        self.tray = tray
        self.conversation_path: Path | None = None
        if conversation_path:
            self.conversation_path = Path(conversation_path)
        self.skills: dict = {}
        self._load_skills()
        self._init_jarvis()
        self._init_conversation()

    # ------------------------------------------------------------------
    # JARVIS subsystem initialization
    # ------------------------------------------------------------------

    def _init_jarvis(self) -> None:
        """Initialize JARVIS subsystems (quick answers, reminders, proactive).

        Each subsystem is optional and gracefully degrades if unavailable.
        All references stored as instance attributes for thread safety.
        """
        self._quick_dispatch = None
        self._reminder_manager = None
        self._proactive_monitor = None
        self._notify_mirror = None

        # Quick answers
        if config.JARVIS_QUICK_ANSWERS:
            try:
                from brain.quick_answers import dispatch as _qa, try_math, try_conversion
                self._quick_dispatch = lambda t: _qa(t) or try_math(t) or try_conversion(t)
                logger.info("JARVIS: Quick answers enabled")
            except Exception as exc:
                logger.debug("JARVIS quick answers unavailable: %s", exc)

        # Reminders
        if config.JARVIS_REMINDERS:
            try:
                from brain.reminders import ReminderManager
                self._reminder_manager = ReminderManager(fire_callback=self._jarvis_speak)
                self._reminder_manager.start()
                logger.info("JARVIS: Reminders enabled")
            except Exception as exc:
                logger.debug("JARVIS reminders unavailable: %s", exc)

        # Proactive monitor
        if config.JARVIS_PROACTIVE:
            try:
                from brain.proactive import ProactiveMonitor
                self._proactive_monitor = ProactiveMonitor(alert_callback=self._jarvis_speak)
                self._proactive_monitor.start()
                logger.info("JARVIS: Proactive monitoring enabled")
            except Exception as exc:
                logger.debug("JARVIS proactive unavailable: %s", exc)

        # Notification mirror
        if config.JARVIS_NOTIFICATION_MIRROR:
            try:
                from brain.notifications import NotificationMirror
                self._notify_mirror = NotificationMirror(speak_callback=self._jarvis_speak)
                self._notify_mirror.start()
                logger.info("JARVIS: Notification mirror enabled")
            except Exception as exc:
                logger.debug("JARVIS notification mirror unavailable: %s", exc)

    def _save_last_response(self, title: str | None = None) -> str:
        """Save the agent's last response to the knowledge base."""
        # Find the last assistant message (skip system prompt)
        for msg in reversed(self.messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                content = msg["content"]
                break
            if msg.get("role") == "tool" and msg.get("content"):
                content = msg["content"]
                break
        else:
            return "Nothing to save. Ask me something first."

        # Generate a title if not provided
        if not title:
            # Use first line or first 50 chars
            title = content.strip().split("\n")[0][:50]
            if len(title) > 40:
                title = title[:40] + "..."

        try:
            from brain.knowledge import save
            result = save(title, content)
            return result
        except Exception as exc:
            return f"Failed to save: {exc}"

    def _jarvis_speak(self, message: str) -> None:
        """Speak a JARVIS message (from reminders, proactive alerts, etc.).

        This is called from background threads, so we print + speak directly
        without going through the main input loop.
        """
        logger.info("JARVIS speaks: %s", message)
        console.print(f"\n[bold yellow]🔔 AILIEN:[/bold yellow] {message}")
        speak(message)

    def _try_quick_answer(self, text: str) -> str | None:
        """Try to handle a query with quick answers before hitting the LLM."""
        # Quick answer dispatch (includes Reddit, YouTube, knowledge base)
        if self._quick_dispatch is not None:
            try:
                result = self._quick_dispatch(text)
                if result:
                    return result
            except Exception:
                pass

        # "save that" — save the last assistant response to knowledge base
        lower = text.lower().strip()
        if lower in ("save that", "save this", "remember that", "keep that", "save to knowledge"):
            return self._save_last_response()
        if lower.startswith("save as ") or lower.startswith("save that as "):
            title = lower.replace("save as ", "").replace("save that as ", "").strip().title()
            return self._save_last_response(title)

        # Reminder commands
        if self._reminder_manager is not None:
            import re
            lower = text.lower().strip()

            # "remind me in X minutes/hours to..." and "remind me to Y in X minutes"
            m = re.match(
                r"remind me (?:in )?(\d+)\s*(min|minute|minutes|m|hour|hours|hr|h|sec|second|seconds|s)\s+(?:to |that |about |:)?(.+)",
                lower,
            )
            if m:
                return self._reminder_manager.set_reminder(
                    m.group(3), **self._parse_duration(m.group(1), m.group(2))
                )
            # "remind me to Y in X minutes"
            m = re.match(
                r"remind me to (.+?) (?:in|after) (\d+)\s*(min|minute|minutes|m|hour|hours|hr|h|sec|second|seconds|s)",
                lower,
            )
            if m:
                return self._reminder_manager.set_reminder(
                    m.group(1), **self._parse_duration(m.group(2), m.group(3))
                )

            # "set/start a timer for X seconds/minutes"
            m = re.match(r"(?:set|start) a timer (?:for |of )?(\d+)\s*(min|minute|minutes|m|hour|hours|hr|h|sec|second|seconds|s)", lower)
            if m:
                return self._reminder_manager.set_reminder(
                    "", **self._parse_duration(m.group(1), m.group(2))
                )

            # "list/show/pending reminders"
            if any(w in lower for w in ["list reminders", "show reminders", "pending reminders", "my reminders"]):
                return self._reminder_manager.list_reminders()

            # "cancel/remove/delete reminder"
            m = re.match(r"(?:cancel|remove|delete|clear)\s+(?:the\s+)?(?:reminder|timer)\s*(.+)?", lower)
            if m:
                identifier = (m.group(1) or "").strip()
                if not identifier:
                    return "Which reminder should I cancel? Try: cancel reminder <text>"
                return self._reminder_manager.cancel_reminder(identifier)

        return None

    @staticmethod
    def _parse_duration(amount: str, unit: str) -> dict:
        """Parse a duration string into kwargs for set_reminder."""
        amount = int(amount)
        if unit in ("hour", "hours", "hr", "h"):
            return {"hours": amount}
        elif unit in ("sec", "second", "seconds", "s"):
            return {"seconds": amount}
        else:
            return {"minutes": amount}

    # ------------------------------------------------------------------
    # Conversation persistence
    # ------------------------------------------------------------------

    def _conversation_filename(self) -> Path:
        """Return the filename for the current conversation.

        Reuses the same filename within a session so autosaves accumulate into
        a single file rather than creating a new file every turn.
        """
        if self.conversation_path:
            return self.conversation_path
        if not hasattr(self, '_session_file'):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._session_file = config.CONVERSATIONS_DIR / f"conversation_{ts}.json"
        return self._session_file

    def save_conversation(self, path: str | Path | None = None) -> Path:
        """Save conversation history to a JSON file."""
        save_path = Path(path) if path else self._conversation_filename()
        try:
            data = {
                "saved_at": datetime.now().isoformat(),
                "message_count": len(self.messages),
                "messages": self.messages,
            }
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("Conversation saved (%d messages) to %s", len(self.messages), save_path)
        except Exception as exc:
            logger.warning("Failed to save conversation: %s", exc)
        return save_path

    def load_conversation(self, path: str | Path) -> bool:
        """Load conversation history from a JSON file. Returns True on success."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            loaded = data.get("messages", [])
            if loaded:
                self.messages = loaded
                logger.info(
                    "Loaded conversation (%d messages) from %s",
                    len(self.messages), path,
                )
                return True
        except Exception as exc:
            logger.warning("Failed to load conversation from %s: %s", path, exc)
        return False

    def _maybe_autosave(self) -> None:
        """Auto-save conversation if enabled."""
        if config.CONVERSATION_AUTO_SAVE:
            self.save_conversation()

    # ------------------------------------------------------------------
    # Skill/plugin loading
    # ------------------------------------------------------------------

    def _load_skills(self) -> None:
        """Load skills from the skills directory."""
        self._skills_execute = None
        self._skills_get_tools = None
        self.skills = {}
        if not config.SKILLS_ENABLED:
            logger.info("Skills disabled by config")
            return
        try:
            from skills import load_all_skills, execute_skill_tool, get_skill_tools
            self._skills_execute = execute_skill_tool
            self._skills_get_tools = get_skill_tools
            self.skills = load_all_skills()
            if self.skills:
                logger.info("Loaded %d skill(s): %s", len(self.skills), ", ".join(self.skills.keys()))
        except Exception as exc:
            logger.warning("Skills not available: %s. Create a skills/ directory with skill modules.", exc)

    # ------------------------------------------------------------------
    # Direct voice-command dispatch (no LLM round-trip for common actions)
    # ------------------------------------------------------------------
    _VOICE_APP_ALIASES: dict[str, str] = {
        "firefox": "firefox",
        "chrome": "google-chrome",
        "chromium": "chromium-browser",
        "edge": "microsoft-edge",
        "terminal": "gnome-terminal",
        "code": "code",
        "vscode": "code",
        "spotify": "spotify",
        "discord": "discord",
        "telegram": "telegram-desktop",
        "slack": "slack",
        "zoom": "zoom",
        "obs": "obs",
        "steam": "steam",
        "gimp": "gimp",
        "blender": "blender",
        "vlc": "vlc",
        "calculator": "gnome-calculator",
        "settings": "gnome-control-center",
        "file manager": "nautilus",
        "text editor": "gedit",
        "writer": "libreoffice --writer",
        "calc": "libreoffice --calc",
        "impress": "libreoffice --impress",
    }

    # Map voice aliases to window class names for xdotool focus.
    _VOICE_WINDOW_CLASSES: dict[str, str] = {
        "firefox": "firefox",
        "chrome": "google-chrome",
        "chromium": "chromium",
        "edge": "microsoft-edge",
        "terminal": "gnome-terminal-server",
        "code": "code",
        "vscode": "code",
        "spotify": "spotify",
        "discord": "discord",
        "telegram": "telegram-desktop",
        "slack": "slack",
        "zoom": "zoom",
        "obs": "obs",
        "steam": "Steam",
        "gimp": "gimp",
        "blender": "blender",
        "vlc": "vlc",
        "calculator": "gnome-calculator",
        "settings": "gnome-control-center",
        "file manager": "nautilus",
        "text editor": "gedit",
        "writer": "soffice",
        "calc": "soffice",
        "impress": "soffice",
    }

    # Map voice aliases to actual psutil process names for safe closing.
    # Only single-word aliases are supported for close commands.
    _VOICE_CLOSE_NAMES: dict[str, str] = {
        "firefox": "firefox",
        "chrome": "chrome",
        "chromium": "chromium",
        "edge": "msedge",
        "terminal": "gnome-terminal-server",
        "code": "code",
        "vscode": "code",
        "spotify": "spotify",
        "discord": "Discord",
        "telegram": "telegram-desktop",
        "slack": "slack",
        "zoom": "zoom",
        "obs": "obs",
        "steam": "steam",
        "gimp": "gimp",
        "blender": "blender",
        "vlc": "vlc",
        "calculator": "gnome-calculator",
        "settings": "gnome-control-center",
        "writer": "soffice.bin",
        "calc": "soffice.bin",
        "impress": "soffice.bin",
    }

    def _try_direct_voice_command(self, text: str) -> str | None:
        """Check if *text* is a direct tool command.  Returns the tool result
        string if handled, or ``None`` if the caller should fall through to
        the LLM.
        """
        import config as _config
        lower = text.lower().strip().rstrip(".,!?;")

        # --- volume -------------------------------------------------------
        if lower in ("volume up", "turn it up", "louder", "increase volume",
                       "turn up the volume", "volume higher", "make it louder"):
            return tools.get_tool("volume_up")()
        if lower in ("volume down", "turn it down", "quieter", "decrease volume",
                       "turn down the volume", "volume lower", "make it quieter"):
            return tools.get_tool("volume_down")()
        if lower in ("mute", "mute audio", "mute sound"):
            return tools.get_tool("mute_volume")()
        if lower in ("unmute", "turn on sound", "restore audio"):
            return tools.get_tool("unmute_volume")()

        # --- media --------------------------------------------------------
        if lower in ("play", "pause", "resume", "stop music",
                       "play music", "pause music"):
            return tools.get_tool("media_play_pause")()
        if lower in ("next", "next track", "skip", "skip song",
                       "next song", "forward"):
            return tools.get_tool("media_next")()
        if lower in ("previous", "last track", "go back", "back",
                       "previous song", "prev"):
            return tools.get_tool("media_previous")()

        # --- keyboard shortcuts -------------------------------------------
        if lower in ("press enter", "hit enter", "press return", "hit return"):
            return tools.get_tool("press_key")(keys="return")
        if lower in ("press escape", "hit escape", "press esc", "hit esc"):
            return tools.get_tool("press_key")(keys="esc")
        if lower in ("press space", "hit space", "press spacebar", "hit spacebar"):
            return tools.get_tool("press_key")(keys="space")
        if lower in ("press tab", "hit tab"):
            return tools.get_tool("press_key")(keys="tab")
        if lower in ("press backspace", "hit backspace"):
            return tools.get_tool("press_key")(keys="backspace")
        if lower in ("press delete", "hit delete"):
            return tools.get_tool("press_key")(keys="delete")
        if lower in ("press up", "press arrow up", "hit up", "hit arrow up"):
            return tools.get_tool("press_key")(keys="up")
        if lower in ("press down", "press arrow down", "hit down", "hit arrow down"):
            return tools.get_tool("press_key")(keys="down")
        if lower in ("press left", "press arrow left", "hit left", "hit arrow left"):
            return tools.get_tool("press_key")(keys="left")
        if lower in ("press right", "press arrow right", "hit right", "hit arrow right"):
            return tools.get_tool("press_key")(keys="right")

        # --- clipboard ----------------------------------------------------
        if lower in ("show clipboard", "what's on my clipboard",
                       "clipboard", "read clipboard"):
            return tools.get_tool("clipboard_get")()

        # --- voice feedback toggle ----------------------------------------
        if lower in ("mute voice", "voice off", "stop talking",
                       "quiet mode", "silence"):
            _config.AGENT_VOICE_FEEDBACK = False
            return "Voice feedback is now off."
        if lower in ("voice on", "unmute voice", "start talking",
                       "talk to me", "speak to me"):
            _config.AGENT_VOICE_FEEDBACK = True
            return "Voice feedback is now on."
        if lower in ("toggle voice", "toggle voice feedback"):
            _config.AGENT_VOICE_FEEDBACK = not _config.AGENT_VOICE_FEEDBACK
            return ("Voice feedback is now on."
                    if _config.AGENT_VOICE_FEEDBACK else
                    "Voice feedback is now off.")

        # --- apps (explicit aliases) --------------------------------------
        for alias, command in self._VOICE_APP_ALIASES.items():
            phrases = (f"open {alias}", f"launch {alias}",
                       f"start {alias}", f"run {alias}")
            if any(p in lower for p in phrases):
                return tools.get_tool("launch_app")(command=command)

        # --- close apps ---------------------------------------------------
        for alias, proc_name in self._VOICE_CLOSE_NAMES.items():
            phrases = (f"close {alias}", f"kill {alias}",
                       f"stop {alias}", f"end {alias}", f"quit {alias}")
            if any(p in lower for p in phrases):
                return tools.get_tool("kill_process")(name=proc_name)

        # --- window management --------------------------------------------
        if lower in ("minimize window", "minimize", "minimise", "minimise window"):
            return tools.get_tool("minimize_window")()
        if lower in ("maximize window", "maximize", "maximise", "maximise window"):
            return tools.get_tool("maximize_window")()
        if lower in ("restore window", "restore", "unmaximize", "normal size", "normal window"):
            return tools.get_tool("restore_window")()

        for alias, class_name in self._VOICE_WINDOW_CLASSES.items():
            phrases = (f"switch to {alias}", f"focus {alias}",
                       f"bring {alias} to front", f"go to {alias}")
            if any(p in lower for p in phrases):
                return tools.get_tool("focus_window")(class_name=class_name)

        # Unknown commands fall through to the LLM for safety.
        return None

    def _set_status(self, status: str) -> None:
        """Update the GUI overlay and tray icon status if available."""
        if self.overlay is not None:
            self.overlay.put_status(status)
        if self.tray is not None:
            self.tray.put_status(status)

    def _init_conversation(self) -> None:
        """Reset conversation history."""
        prompt = SYSTEM_PROMPT
        logger.debug("System prompt length: %d", len(prompt))
        self.messages = [
            {"role": "system", "content": prompt},
        ]

    def _trim_history(self, max_messages: int | None = None) -> None:
        """Trim conversation history to stay within context window.
        Keeps system prompt + last N messages (default from config).
        """
        limit = max_messages or config.CONVERSATION_MAX_HISTORY
        if len(self.messages) > limit + 1:
            # Keep system prompt, drop oldest user/assistant/tool messages
            system = self.messages[0]
            self.messages = [system] + self.messages[-limit:]

    def _ensure_transcriber(self) -> None:
        """Lazy-load the transcriber."""
        if self.transcriber is None:
            self.transcriber = WhisperTranscriber()

    def _ask_confirmation(self, tool_name: str, params: dict) -> bool:
        """Ask user for confirmation before dangerous actions."""
        console.print(
            f"\n[bold yellow]⚠️  The agent wants to run:[/bold yellow] [bold]{tool_name}[/bold]"
        )
        for k, v in params.items():
            console.print(f"   {k}: {v!r}")
        console.print("[dim]Type 'yes' to allow, anything else to block.[/dim]")
        try:
            answer = console.input("Allow? ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "no"
        return answer in ("yes", "y", "yeah", "yep")

    def _execute_with_confirmation(self, name: str, args: dict) -> str:
        """Execute a tool, prompting for confirmation if needed."""
        if SafetyGuard.requires_confirmation(name, args):
            if not self._ask_confirmation(name, args):
                return "User denied permission."

        if name in ("run_shell", "shell"):
            try:
                SafetyGuard.block_dangerous_shell(args.get("command", ""))
            except ValueError as exc:
                return f"Safety block: {exc}"

        func = tools.get_tool(name)
        print_tool_call(name, args)
        try:
            return func(**args)
        except Exception as exc:
            logger.exception(f"Tool {name} failed")
            return f"Error executing {name}: {exc}"

    def _get_all_tools(self) -> list[dict]:
        """Return all available tools, including skill tools."""
        all_tools = list(tools.TOOLS)
        try:
            if self._skills_get_tools is not None:
                for td in self._skills_get_tools():
                    all_tools.append(td.to_openai_schema())
        except Exception:
            pass
        return all_tools

    def _execute_skill_tool(self, name: str, **kwargs) -> str | None:
        """Try to execute a skill tool. Returns result or None if not a skill tool."""
        if self._skills_execute is None:
            return None
        try:
            return self._skills_execute(name, **kwargs)
        except Exception:
            pass
        return None

    def _chat_with_tools(self, user_text: str) -> str:
        """Send user message to LLM and handle tool calls with confirmation."""

        # JARVIS quick answers: intercept before LLM round-trip
        quick = self._try_quick_answer(user_text)
        if quick is not None:
            self.messages.append({"role": "user", "content": user_text})
            self.messages.append({"role": "assistant", "content": quick})
            self._maybe_autosave()
            return quick

        self._trim_history()
        self.messages.append({"role": "user", "content": user_text})

        all_tools = self._get_all_tools()

        for round_num in range(10):
            self._trim_history()
            message = self.client.chat(self.messages, tools=all_tools)
            self.messages.append(message)

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                self._maybe_autosave()
                return message.get("content", "")

            # Execute each tool call
            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                raw_args = func.get("arguments", "{}")
                call_id = tc.get("id", "")

                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}
                elif isinstance(raw_args, dict):
                    args = raw_args
                else:
                    args = {}

                # Try skill tools first, then built-in tools
                skill_result = self._execute_skill_tool(name, **args)
                if skill_result is not None:
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": skill_result,
                    })
                else:
                    result = self._execute_with_confirmation(name, args)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": str(result),
                    })

        self._maybe_autosave()
        return message.get("content", "")

    def _run_input_loop(
        self,
        *,
        start_freebuff: bool = False,
        voice_enabled: bool = True,
    ) -> None:
        """Shared input loop for text and freebuff modes.

        Supports both typed text and wake-word voice input via a producer-consumer
        queue.  When *start_freebuff* is True the output is minimal inline text
        (no panels).  When *voice_enabled* is False the wake-word detector is not
        started.  Mode can be toggled mid-session with /freebuff and /fancy.
        """
        self._ensure_transcriber()
        self._set_status("idle")

        command_queue: Queue[tuple[str, str]] = Queue()
        detector: "WakeWordDetector | OpenWakeWordDetector | None" = None  # noqa: F821

        if voice_enabled:
            def on_wake_word(command_text: str) -> None:
                command_queue.put(("voice", command_text))

            detector = create_detector(
                transcriber=self.transcriber,
                callback=on_wake_word,
                recorder=self.recorder,
                chunk_max_duration=config.WAKE_WORD_CHUNK_MAX_DURATION,
                chunk_silence_duration=config.WAKE_WORD_CHUNK_SILENCE_DURATION,
            )
            detector.start()

        _text_alive = True

        def _make_prompt(freebuff: bool) -> str:
            return "> " if freebuff else "[bold green]You:[/bold green] "

        def _text_input_loop(freebuff: bool) -> None:
            while _text_alive:
                try:
                    user_input = console.input(_make_prompt(freebuff)).strip()
                except (EOFError, KeyboardInterrupt):
                    command_queue.put(("quit", ""))
                    break
                if not user_input:
                    continue
                command_queue.put(("text", user_input))

        # Start with the requested mode
        freebuff = start_freebuff
        _sleeping = False
        text_thread = threading.Thread(target=lambda: _text_input_loop(freebuff), daemon=True)
        text_thread.start()

        def _set_helpers(fb: bool):
            """Return the appropriate print helpers for the current mode."""
            if fb:
                return fb_print_user, fb_print_agent, fb_print_info, fb_print_error
            else:
                def _info(t: str) -> None:
                    console.print(f"[dim]{t}[/dim]")
                def _err(t: str) -> None:
                    console.print(f"[bold red]Error: {t}[/bold red]")
                return print_user_message, print_agent_message, _info, _err

        try:
            while True:
                cmd_type, text = command_queue.get()
                p_user, p_agent, p_info, p_err = _set_helpers(freebuff)

                if cmd_type == "quit":
                    console.print("Goodbye!")
                    break

                # While sleeping, only "wake up" voice commands are processed
                if _sleeping:
                    lower = text.lower().strip()
                    if lower in ("start listening", "resume listening", "wake up", "wake"):
                        _sleeping = False
                        p_info("Resumed listening.")
                        speak("I'm listening again.")
                    else:
                        pass  # ignore everything else while sleeping
                    continue

                if cmd_type == "text":
                    lower = text.lower().strip()
                    if lower in ("quit", "exit", "q", "bye"):
                        console.print("Goodbye!")
                        break
                    if lower == "clear":
                        self._init_conversation()
                        p_info("Conversation cleared.")
                        continue
                    if lower == "/freebuff" and not freebuff:
                        p_info("Switching to freebuff mode...")
                        freebuff = True
                        continue
                    if lower == "/fancy" and freebuff:
                        p_info("Switching to fancy mode...")
                        freebuff = False
                        continue
                    if lower in ("/mute", "/voiceoff"):
                        import config as _config
                        _config.AGENT_VOICE_FEEDBACK = False
                        p_info("Voice feedback muted.")
                        continue
                    if lower in ("/voice", "/unmute", "/voiceon"):
                        import config as _config
                        _config.AGENT_VOICE_FEEDBACK = True
                        p_info("Voice feedback enabled.")
                        speak("Voice feedback is now on.")
                        continue
                    p_user(text)
                    user_text = text
                elif cmd_type == "voice":
                    if detector is not None:
                        detector.pause()
                    if not text:
                        # Wake word with no command — record follow-up
                        p_info("Wake word detected! Listening for command...")
                        try:
                            self._set_status("listening")
                            audio = self.recorder.record_until_silence()
                            self._set_status("thinking")
                        except RuntimeError:
                            p_err("Microphone unavailable.")
                            speak("Microphone unavailable.")
                            if detector is not None:
                                detector.resume()
                            continue
                        if audio.size == 0:
                            p_info("No audio detected.")
                            speak("I didn't hear anything.")
                            if detector is not None:
                                detector.resume()
                            continue
                        p_info("Transcribing...")
                        text = self.transcriber.transcribe(audio)
                        if not text:
                            p_info("Could not understand audio.")
                            speak("I didn't catch that.")
                            if detector is not None:
                                detector.resume()
                            continue
                    # Voice control commands (common to both modes)
                    lower = text.lower().strip()
                    if lower in ("quit", "exit", "goodbye", "shut down"):
                        speak("Goodbye!")
                        console.print("Goodbye!")
                        break
                    if lower in ("clear", "clear conversation", "reset"):
                        self._init_conversation()
                        p_info("Conversation cleared.")
                        speak("Conversation cleared.")
                        if detector is not None:
                            detector.resume()
                        continue
                    if lower in ("go to sleep", "sleep", "stop listening"):
                        _sleeping = True
                        p_info("Going to sleep. Say 'Hey AILIEN, wake up' to resume.")
                        speak("Going to sleep. Say wake up to resume.")
                        continue
                    if lower in ("wake up", "wake", "resume listening"):
                        p_info("Already awake.")
                        speak("I'm already listening.")
                        continue
                    if lower in ("screenshot", "take screenshot", "capture screen"):
                        try:
                            result = tools.get_tool("take_screenshot")()
                            if freebuff:
                                p_agent(result)
                            else:
                                console.print(Panel(Text(result, style="cyan"), title="[bold]Screenshot[/bold]", border_style="cyan"))
                            speak("Screenshot taken. " + " ".join(result.splitlines())[:200])
                        except Exception as exc:
                            p_err(f"Screenshot failed: {exc}")
                            speak("Sorry, I couldn't take a screenshot.")
                        if detector is not None:
                            detector.resume()
                        self._set_status("idle")
                        continue
                    if lower in ("status", "system status", "computer status"):
                        try:
                            info = tools.get_tool("system_info")()
                            if freebuff:
                                p_agent(info)
                            else:
                                console.print(Panel(Text(info, style="cyan"), title="[bold]System Status[/bold]", border_style="cyan"))
                            speak("System status: " + " ".join(info.splitlines()))
                        except Exception as exc:
                            p_err(f"Could not get system status: {exc}")
                            speak("Sorry, I couldn't get the system status.")
                        if detector is not None:
                            detector.resume()
                        self._set_status("idle")
                        continue

                    # Try direct tool commands (volume, media, apps, etc.)
                    direct_result = self._try_direct_voice_command(text)
                    if direct_result is not None:
                        if freebuff:
                            p_agent(direct_result)
                        else:
                            console.print(Panel(Text(direct_result, style="cyan"), title="[bold]Action[/bold]", border_style="cyan"))
                        speak(direct_result)
                        if detector is not None:
                            detector.resume()
                        self._set_status("idle")
                        continue

                    p_user(text)
                    user_text = text
                else:
                    continue

                # Pause detector while processing any command (prevents self-triggering on TTS)
                if detector is not None:
                    detector.pause()

                self._set_status("thinking")
                if freebuff:
                    p_info("Thinking...")
                    response = self._chat_with_tools(user_text)
                else:
                    with console.status("[cyan]Thinking...[/cyan]"):
                        response = self._chat_with_tools(user_text)
                p_agent(response)
                self._set_status("speaking")
                speak(response)
                self._set_status("idle")
                if detector is not None:
                    detector.resume()
        finally:
            _text_alive = False
            if detector is not None:
                detector.stop()

    def run_text_mode(self) -> None:
        """Interactive text mode with optional wake-word voice input."""
        console.print(
            Panel(
                Text(
                    "AILIEN - Text Mode\n"
                    "Type your command or 'quit' to exit.\n"
                    "Say 'Hey AILIEN' at any time to speak a command.\n"
                    "Type /freebuff for minimal inline style.\n"
                    "Type /mute or /voice to toggle TTS feedback.",
                    justify="center",
                ),
                border_style="cyan",
            )
        )
        self._run_input_loop(start_freebuff=False, voice_enabled=True)

    def run_freebuff_mode(self) -> None:
        """Minimal inline terminal mode (like freebuff) — no panels, just plain text."""
        console.print("\n[bold]AILIEN Freebuff Mode[/bold] — minimal inline chat")
        console.print("[dim]Type /fancy to switch back to rich panels. Say 'Hey AILIEN' for voice.[/dim]")
        console.print("[dim]Type /mute or /voice to toggle TTS feedback.[/dim]\n")
        self._run_input_loop(start_freebuff=True, voice_enabled=True)

    def run_voice_mode(self) -> None:
        """Voice-interactive mode."""
        self._ensure_transcriber()
        self._set_status("idle")
        console.print(
            Panel(
                Text(
                    "AILIEN - Voice Mode\n"
                    "Speak after the beep. Silence for 2 seconds stops recording.\n"
                    "Type 'q' and Enter to quit, 't' to switch to text input.",
                    justify="center",
                ),
                border_style="cyan",
            )
        )

        while True:
            try:
                console.print("\n[dim]Press Enter to record, or type 'q' to quit / 't' for text:[/dim]")
                prompt = console.input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("\nGoodbye!")
                break

            if prompt == "q":
                console.print("Goodbye!")
                break
            if prompt == "t":
                self.run_text_mode()
                break
            if prompt == "clear":
                self._init_conversation()
                console.print("[dim]Conversation cleared.[/dim]")
                continue

            # Record audio
            console.print("[bold yellow]🎙️  Recording...[/bold yellow] (speak now)")
            self._set_status("listening")
            audio = self.recorder.record_until_silence()
            self._set_status("thinking")
            if audio.size == 0:
                console.print("[dim]No audio detected.[/dim]")
                self._set_status("idle")
                continue

            console.print("[dim]Transcribing...[/dim]")
            text = self.transcriber.transcribe(audio)
            if not text:
                console.print("[dim]Could not understand audio.[/dim]")
                self._set_status("idle")
                continue

            print_user_message(text)
            with console.status("[cyan]Thinking...[/cyan]"):
                response = self._chat_with_tools(text)
            print_agent_message(response)
            self._set_status("speaking")
            speak(response)
            self._set_status("idle")

    def run_wake_word_mode(self) -> None:
        """Continuous wake-word listening mode."""
        self._ensure_transcriber()
        # Pre-load whisper model so wake word works immediately on first utterance
        try:
            import numpy as np
            self._set_status("thinking")
            logger.info("Pre-loading whisper model...")
            self.transcriber.transcribe(np.zeros(16000, dtype=np.float32))
            logger.info("Whisper model loaded")
        except Exception:
            pass
        self._set_status("listening")
        console.print(
            Panel(
                Text(
                    "AILIEN - Wake Word Mode\n"
                    "Say 'Hey Jarvis' followed by your command.\n"
                    "Voice controls: 'go to sleep', 'wake up', 'text mode', 'screenshot', 'status', 'quit'\n"
                    "The agent listens continuously in the background.\n"
                    "Press Ctrl+C to quit.",
                    justify="center",
                ),
                border_style="cyan",
            )
        )
        console.print(
            "[dim]Voice controls: volume up/down, mute, play/pause, next/previous, "
            "screenshot, status, open/close apps, press enter/escape/arrows, "
            "minimize/maximize/restore window, switch to <app>, "
            "show clipboard, clear, go to sleep, wake up, quit, "
            "mute voice / voice on / toggle voice[/dim]\n"
        )

        command_queue: Queue[str] = Queue()
        _sleeping = False
        _should_quit = False

        def on_wake_word(command_text: str) -> None:
            command_queue.put(command_text)

        detector = create_detector(
            transcriber=self.transcriber,
            callback=on_wake_word,
            recorder=self.recorder,
            chunk_max_duration=config.WAKE_WORD_CHUNK_MAX_DURATION,
            chunk_silence_duration=config.WAKE_WORD_CHUNK_SILENCE_DURATION,
        )
        detector.start()
        console.print("[dim]Listening for wake word...[/dim]")

        def _handle_special_command(cmd: str) -> bool:
            """Check for voice control commands. Returns True if handled."""
            nonlocal _sleeping, _should_quit
            lower = cmd.lower().strip()

            # Sleep commands (detector keeps running so it can hear 'wake up')
            if lower in ("stop listening", "pause listening", "go to sleep", "sleep"):
                _sleeping = True
                console.print("[dim]Going to sleep. Say 'Hey AILIEN, wake up' to resume.[/dim]")
                speak("Going to sleep. Say wake up to resume.")
                return True

            # Wake commands
            if lower in ("start listening", "resume listening", "wake up", "wake"):
                if _sleeping:
                    _sleeping = False
                    console.print("[dim]Resumed listening.[/dim]")
                    speak("I'm listening again.")
                else:
                    console.print("[dim]Already awake.[/dim]")
                return True

            # Switch to text mode
            if lower in ("text mode", "switch to text", "keyboard mode"):
                console.print("[dim]Switching to text mode...[/dim]")
                speak("Switching to text mode.")
                self.run_text_mode()
                return True

            # Quit commands
            if lower in ("quit", "exit", "goodbye", "shut down"):
                _should_quit = True
                console.print("[dim]Shutting down...[/dim]")
                speak("Goodbye!")
                return True

            # Status command
            if lower in ("status", "system status", "computer status"):
                try:
                    info = tools.get_tool("system_info")()
                    console.print(Panel(Text(info, style="cyan"), title="[bold]System Status[/bold]", border_style="cyan"))
                    speak("System status: " + " ".join(info.splitlines()))
                except Exception as exc:
                    console.print(f"[dim]Could not get system status: {exc}[/dim]")
                    speak("Sorry, I couldn't get the system status.")
                return True

            # Screenshot command
            if lower in ("screenshot", "take screenshot", "capture screen"):
                try:
                    self._set_status("thinking")
                    result = tools.get_tool("take_screenshot")()
                    console.print(Panel(Text(result, style="cyan"), title="[bold]Screenshot[/bold]", border_style="cyan"))
                    speak("Screenshot taken. " + " ".join(result.splitlines())[:200])
                except Exception as exc:
                    console.print(f"[dim]Screenshot failed: {exc}[/dim]")
                    speak("Sorry, I couldn't take a screenshot.")
                return True

            # Clear conversation
            if lower in ("clear", "clear conversation", "reset"):
                self._init_conversation()
                console.print("[dim]Conversation cleared.[/dim]")
                speak("Conversation cleared.")
                return True

            # Direct tool commands (volume, media, apps, etc.)
            direct_result = self._try_direct_voice_command(cmd)
            if direct_result is not None:
                console.print(Panel(Text(direct_result, style="cyan"), title="[bold]Action[/bold]", border_style="cyan"))
                speak(direct_result)
                return True

            return False

        try:
            while not _should_quit:
                try:
                    command = command_queue.get(timeout=0.5)
                except Empty:
                    continue

                # While sleeping, only wake-up commands are processed
                if _sleeping:
                    lower = command.lower().strip()
                    if lower in ("start listening", "resume listening", "wake up", "wake"):
                        _sleeping = False
                        console.print("[dim]Resumed listening.[/dim]")
                        speak("I'm listening again.")
                    else:
                        # Ignore all other commands while sleeping
                        pass
                    continue

                detector.pause()
                self._set_status("thinking")

                if not command:
                    # Wake word said without a command — record a follow-up
                    console.print("[bold yellow]🎙️  Wake word detected! Listening for command...[/bold yellow]")
                    try:
                        self._set_status("listening")
                        audio = self.recorder.record_until_silence()
                        self._set_status("thinking")
                    except RuntimeError:
                        console.print("[bold red]🚫 Microphone unavailable.[/bold red]")
                        speak("Microphone unavailable.")
                        detector.resume()
                        self._set_status("listening")
                        continue
                    if audio.size == 0:
                        console.print("[dim]No audio detected. Try speaking louder or closer to the mic.[/dim]")
                        speak("I didn't hear anything. Please try again.")
                        detector.resume()
                        self._set_status("listening")
                        continue
                    console.print("[dim]Transcribing...[/dim]")
                    command = self.transcriber.transcribe(audio)
                    if not command:
                        console.print("[dim]Could not understand audio. Try speaking more clearly.[/dim]")
                        speak("I didn't catch that. Please try again.")
                        detector.resume()
                        self._set_status("listening")
                        continue

                # Handle voice control commands first
                if _handle_special_command(command):
                    detector.resume()
                    if not _sleeping:
                        console.print("[dim]Listening for wake word...[/dim]")
                        self._set_status("listening")
                    continue

                print_user_message(command)
                with console.status("[cyan]Thinking...[/cyan]"):
                    response = self._chat_with_tools(command)
                print_agent_message(response)
                self._set_status("speaking")
                speak(response)
                console.print("[dim]Listening for wake word...[/dim]")
                self._set_status("listening")
                detector.resume()
        except KeyboardInterrupt:
            console.print("\n[dim]Stopping wake word listener...[/dim]")
        finally:
            detector.stop()
            console.print("Goodbye!")

    def run_window_mode(self, voice_window) -> None:
        """Voice control window mode.

        Opens the VoiceWindow GUI and processes commands (text or voice)
        through the agent, sending results back to the window.
        """
        self._ensure_transcriber()
        self._voice_window = voice_window
        self._ww_detector = None

        # Pre-load whisper model
        try:
            import numpy as np
            self._set_status("thinking")
            logger.info("Pre-loading whisper model...")
            self.transcriber.transcribe(np.zeros(16000, dtype=np.float32))
            logger.info("Whisper model loaded")
        except Exception:
            pass

        # ------------------------------------------------------------------
        # Wake word command processing
        # ------------------------------------------------------------------
        def _process_wake_word_command(command_text: str) -> None:
            """Process a wake word command: if empty, record follow-up audio."""
            if not command_text:
                # Wake word said without a command — record follow-up
                voice_window.append_message("system", "Wake word detected! Listening for command...")
                try:
                    self._set_status("listening")
                    audio = self.recorder.record_until_silence()
                    self._set_status("thinking")
                except RuntimeError:
                    voice_window.append_message("error", "Microphone unavailable.")
                    self._set_status("idle")
                    if self._ww_detector:
                        self._ww_detector.resume()
                    return
                if audio.size == 0:
                    voice_window.append_message("system", "No audio detected.")
                    self._set_status("idle")
                    if self._ww_detector:
                        self._ww_detector.resume()
                    return
                voice_window.append_message("system", "Transcribing...")
                command_text = self.transcriber.transcribe(audio)
                if not command_text:
                    voice_window.append_message("system", "Could not understand audio.")
                    self._set_status("idle")
                    if self._ww_detector:
                        self._ww_detector.resume()
                    return

            # Send command through the same processing pipeline
            voice_window.append_message("user", command_text)
            self._set_status("thinking")

            def _maybe_resume_detector():
                """Resume the wake word detector only if voice is still active."""
                if self._ww_detector and voice_window.voice_active:
                    self._ww_detector.resume()

            # Direct commands
            direct = self._try_direct_voice_command(command_text)
            if direct:
                voice_window.append_message("agent", direct)
                self._set_status("speaking")
                speak(direct)
                self._set_status("idle")
                _maybe_resume_detector()
                return

            # Quick answers
            quick = self._try_quick_answer(command_text)
            if quick:
                voice_window.append_message("agent", quick)
                self._set_status("speaking")
                speak(quick)
                self._set_status("idle")
                _maybe_resume_detector()
                return

            # Full LLM processing
            def process():
                response = self._chat_with_tools(command_text)
                voice_window.append_message("agent", response)
                self._set_status("speaking")
                speak(response)
                self._set_status("idle")
                # Only resume if voice is still active (user hasn't paused)
                _maybe_resume_detector()

            threading.Thread(target=process, daemon=True).start()

        # ------------------------------------------------------------------
        # Create wake word detector
        # ------------------------------------------------------------------
        def _on_wake_word(command_text: str) -> None:
            """Callback from wake word detector — pause detector and queue command."""
            if self._ww_detector:
                self._ww_detector.pause()
            _process_wake_word_command(command_text)

        self._ww_detector = create_detector(
            transcriber=self.transcriber,
            callback=_on_wake_word,
            recorder=self.recorder,
            chunk_max_duration=config.WAKE_WORD_CHUNK_MAX_DURATION,
            chunk_silence_duration=config.WAKE_WORD_CHUNK_SILENCE_DURATION,
        )

        # ------------------------------------------------------------------
        # Text command processing (from window text input)
        # ------------------------------------------------------------------
        def on_command(text: str) -> None:
            """Callback when user submits text from the window."""
            self._set_status("thinking")

            # Pause wake word detector while processing text command
            if self._ww_detector:
                self._ww_detector.pause()

            # Direct commands
            direct = self._try_direct_voice_command(text)
            if direct:
                voice_window.append_message("agent", direct)
                self._set_status("speaking")
                speak(direct)
                self._set_status("idle")
                if self._ww_detector and voice_window.voice_active:
                    self._ww_detector.resume()
                return

            # Quick answers
            quick = self._try_quick_answer(text)
            if quick:
                voice_window.append_message("agent", quick)
                self._set_status("speaking")
                speak(quick)
                self._set_status("idle")
                if self._ww_detector and voice_window.voice_active:
                    self._ww_detector.resume()
                return

            # Full LLM processing
            def process():
                response = self._chat_with_tools(text)
                voice_window.append_message("agent", response)
                self._set_status("speaking")
                speak(response)
                self._set_status("idle")
                # Resume detector only if voice is still active
                if self._ww_detector and voice_window.voice_active:
                    self._ww_detector.resume()

            threading.Thread(target=process, daemon=True).start()

        def on_stop() -> None:
            """Callback when user hits STOP to interrupt."""
            logger.info("User interrupted via STOP button")
            cancel_speech()
            self._set_status("idle")

        def on_voice_toggle(active: bool) -> None:
            """Callback when user toggles voice listening via the LISTEN/PAUSE button.

            Actually starts/pauses the wake word detector.
            """
            logger.info("Voice toggled %s by user", "ON" if active else "OFF")
            if self._ww_detector is None:
                voice_window.append_message("error", "Wake word detector not available.")
                return

            if active:
                self._ww_detector.resume()
                voice_window.append_message("system", f"Listening for wake phrases: {', '.join(config.AGENT_WAKE_WORDS[:6])}...")
                self._set_status("listening")
            else:
                self._ww_detector.pause()
                voice_window.append_message("system", "Voice detection paused. Click LISTEN to re-activate.")
                self._set_status("idle")

        # ------------------------------------------------------------------
        # Wire up callbacks and start
        # ------------------------------------------------------------------
        voice_window.set_callbacks(
            on_command=on_command,
            on_stop=on_stop,
            on_voice_toggle=on_voice_toggle,
        )
        voice_window.append_message("system", "AILIEN Voice Control ready. Type a command or click LISTEN to use voice.")
        voice_window.show()

        # Start voice detection by default
        if self._ww_detector:
            self._ww_detector.start()
            voice_window.set_voice_active(True)  # Thread-safe: shows "PAUSE" button state
            self._set_status("listening")

    def run_single_command(self, command: str) -> None:
        """Execute a single command and exit."""
        self._set_status("thinking")
        print_user_message(command)
        with console.status("[cyan]Thinking...[/cyan]"):
            response = self._chat_with_tools(command)
        print_agent_message(response)
        self._set_status("speaking")
        speak(response)
        self._set_status("idle")


def main() -> None:
    parser = argparse.ArgumentParser(description="AILIEN — AI computer control assistant")
    parser.add_argument("--text", "-t", action="store_true", help="Start in text mode")
    parser.add_argument("--voice", "-v", action="store_true", help="Start in voice mode")
    parser.add_argument("--wake-word", "-w", action="store_true", help="Start in wake-word listening mode")
    parser.add_argument("--command", "-c", type=str, help="Run a single command and exit")
    parser.add_argument("--no-voice-feedback", action="store_true", help="Disable TTS feedback")
    parser.add_argument("--no-overlay", action="store_true", help="Disable the GUI status overlay")
    parser.add_argument("--gui", "-g", action="store_true", help="Open the Voice Control window (start/pause voice, stop mid-sentence, text input)")
    parser.add_argument("--freebuff", "-f", action="store_true", help="Start in minimal inline freebuff mode")
    parser.add_argument("--serve", "-s", action="store_true", help="Start the HTTP API server for Open WebUI integration")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="API server host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="API server port (default 8000)")
    parser.add_argument("--conversation", type=str, default=None, help="Load a previous conversation file (.json)")
    parser.add_argument("--list-conversations", action="store_true", help="List saved conversation files and exit")
    parser.add_argument("--save-conversation", type=str, default=None, help="Save conversation to a specific file after command completes")
    parser.add_argument("--daemon", "-d", action="store_true", help="Run in background daemon mode (tray icon + wake word, no terminal console)")
    args = parser.parse_args()

    if args.daemon:
        # PID file to prevent duplicate daemon instances
        pid_file = config.CACHE_DIR / "ailien_daemon.pid"
        if pid_file.exists():
            try:
                old_pid = int(pid_file.read_text().strip())
                # Check if the process is still running
                os.kill(old_pid, 0)
                # Process is still alive — refuse to start another
                print(f"AILIEN is already running (PID {old_pid}).")
                notify("AILIEN", f"Already running (PID {old_pid}). Look for the 👽 icon in your system tray.")
                return
            except (ProcessLookupError, ValueError, OSError):
                # Process is dead or PID invalid — remove stale file
                pid_file.unlink(missing_ok=True)
        # Write our PID
        pid_file.write_text(str(os.getpid()))

        config.AGENT_VOICE_FEEDBACK = True
        config.JARVIS_PROACTIVE = True
        args.wake_word = True
        args.no_overlay = True  # Tray icon handles status — no floating window needed
        logger.info("Starting in daemon mode")
        notify("AILIEN", "Running in background. Say 'Hey Jarvis' to wake me up")

    if args.list_conversations:
        conv_dir = config.CONVERSATIONS_DIR
        if not conv_dir.exists():
            print("No saved conversations.")
            return
        convs = sorted(conv_dir.glob("conversation_*.json"))
        if not convs:
            print("No saved conversations.")
            return
        print(f"Saved conversations ({len(convs)}):")
        for c in convs:
            size = c.stat().st_size
            mtime = datetime.fromtimestamp(c.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  {c.name}  ({size} bytes, saved {mtime})")
        return

    if args.serve:
        from api_server import run_server
        run_server(host=args.host, port=args.port)
        return

    if args.no_voice_feedback:
        config.AGENT_VOICE_FEEDBACK = False

    if not args.no_overlay:
        _print_typing_banner(console)

    overlay = None
    voice_window = None

    if args.gui:
        # Use the VoiceWindow as the primary interface
        try:
            from gui.voice_window import VoiceWindow
            voice_window = VoiceWindow()
            # Give it a moment to start the tkinter thread
            import time
            time.sleep(0.2)
        except Exception as exc:
            logger.warning(f"Could not create VoiceWindow: {exc}")
    if not args.gui and not args.no_overlay:
        try:
            from gui.overlay import StatusOverlay
            overlay = StatusOverlay()
            overlay.show()
        except Exception as exc:
            logger.warning(f"Could not create GUI overlay: {exc}")

    tray = None
    try:
        from gui.tray import TrayIcon
        tray = TrayIcon(overlay=overlay)
        # Pass VoiceWindow reference so the tray menu can open it
        if voice_window:
            tray.set_voice_window(voice_window)
        tray.start()
    except Exception as exc:
        logger.warning(f"Could not create tray icon: {exc}")

    agent = Agent(overlay=overlay, tray=tray)

    # Load conversation if specified
    if args.conversation:
        conv_path = Path(args.conversation)
        if not conv_path.is_absolute():
            conv_path = config.CONVERSATIONS_DIR / conv_path
        if conv_path.exists():
            if agent.load_conversation(conv_path):
                console.print(f"[dim]Loaded conversation from {conv_path}[/dim]")
        else:
            console.print(f"[yellow]Conversation file not found: {conv_path}[/yellow]")

    notify("AILIEN", "Agent is running 👽")

    def run_agent() -> None:
        try:
            if args.command:
                agent.run_single_command(args.command)
            elif args.wake_word:
                agent.run_wake_word_mode()
            elif args.voice:
                agent.run_voice_mode()
            elif args.gui:
                if voice_window:
                    agent.run_window_mode(voice_window)
                else:
                    agent.run_text_mode()
            elif args.freebuff:
                agent.run_freebuff_mode()
            else:
                agent.run_text_mode()
        finally:
            notify("AILIEN", "Agent stopped")
            # Stop wake word detector (releases microphone)
            if hasattr(agent, '_ww_detector') and agent._ww_detector:
                try:
                    agent._ww_detector.stop()
                except Exception:
                    pass
            # Clean up PID file
            try:
                pid_file = config.CACHE_DIR / "ailien_daemon.pid"
                if pid_file.exists():
                    pid_file.unlink()
            except Exception:
                pass
            if overlay:
                overlay.put_status("closed")
            if tray:
                tray.stop()
            if voice_window:
                voice_window.close()

    # Save conversation after single command if requested
    if args.command and args.save_conversation:
        agent.save_conversation(args.save_conversation)

    if args.gui and voice_window:
        # VoiceWindow mode — tkinter runs in its own thread, just start agent
        run_agent()
        # Keep main thread alive while tkinter thread runs
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            cancel_speech()
            if hasattr(agent, '_ww_detector') and agent._ww_detector:
                try:
                    agent._ww_detector.stop()
                except Exception:
                    pass
            if voice_window:
                voice_window.close()
            if tray:
                tray.stop()
    elif overlay:
        overlay.start_agent(run_agent)
        overlay.run()
    else:
        run_agent()


if __name__ == "__main__":
    main()
