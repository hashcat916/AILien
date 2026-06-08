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

import config
import tools
import tools.apps
import tools.browser
import tools.browser_extras
import tools.code_tools
import tools.email_tool
import tools.files
import tools.keyboard
import tools.mouse
import tools.notes
import tools.productivity
import tools.screen
import tools.shell
import tools.system
import tools.display_tools
import tools.media_tools
import tools.torrent_tools
import tools.reminder_tools
import tools.automation_tools
import tools.feature_toggle
import tools.website_tools
import tools.server_tools
import tools.domain_tools
import tools.create_tool
import tools.learn_tools
import tools.documentation_tools
import tools.project_tools
import tools.utility_tools
import tools.lifestyle_tools
import tools.reasoning_tools
import tools.agent_browser_tools
import tools.course_tools
import tools.gaming_tools
from brain.conversation_learner import auto_learn_from_response, auto_learn_from_tool
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
    fancy_print_agent,
    fancy_print_user,
    fancy_print_tool,
    notify,
    print_header,
    print_user,
    print_agent,
    print_tool,
    print_status,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_divider,
    print_panel,
    show_thinking,
    hide_thinking,
    ask_confirmation,
    reset_speech,
    setup_crash_logging,
    setup_logging,
    speak,
)


console = Console()
logger = setup_logging()
setup_crash_logging()


def _print_banner() -> None:
    """Print a clean, professional startup banner."""
    print_header("AILIEN", " — AI Computer Control")

SYSTEM_PROMPT = """You are AILIEN. You help the user control their computer by calling tools.

Available tools include:

=== MOUSE & KEYBOARD ===
mouse_move, mouse_click, mouse_scroll, mouse_drag, get_mouse_position
type_text, press_key, clipboard_get, clipboard_set

=== SCREEN ===
take_screenshot, read_screen_text

=== APPS ===
launch_app, list_running_apps, kill_process, find_process

=== FILES ===
list_directory, read_file, find_file, open_file

=== SYSTEM ===
system_info, get_active_window, set_volume

=== BROWSER (Firefox) ===
open_url — open a URL in the default browser
browser_navigate — navigate Firefox to a URL (focuses browser, types in address bar)
browser_search — search Google or Wikipedia (opens new tab)
browser_get_info — get the current page title and URL
browser_click_link — click a link on the page by its visible text
browser_scroll — scroll the page up/down
browser_fill_form — type into a form field by its label
browser_find — search for text on the page
browser_new_tab — open a new tab
browser_close_tab — close the current tab
browser_go_back — go to previous page
browser_go_forward — go to next page
browser_refresh — reload the page
browser_switch_tab — switch to next/previous tab
get_webpage_text — fetch a URL and extract readable text (no browser needed)

=== LOCAL MEDIA ===
play_media — search for and play a local movie, music file, or video by name
list_media — list available media files in your Music, Videos, Movies folders

=== YOUTUBE ===
youtube_search — search YouTube for videos matching a query (titles, channels, durations, links)
play_youtube — search YouTube and play the best matching video (plays locally or opens in browser)
youtube_trending — show currently trending videos on YouTube

=== DISPLAY ===
set_brightness — set screen brightness to a percentage (0–100)
brightness_up — increase brightness
brightness_down — decrease brightness
get_brightness — show current brightness

=== TORRENTS (Transmission) ===
add_torrent — download a torrent via magnet link or .torrent URL
torrent_status — show status of all active torrents
torrent_pause — pause a torrent by its ID
torrent_resume — resume a paused torrent by its ID

=== MEDIA ===
media_play_pause — toggle play/pause in Firefox (YouTube, Spotify, etc.)
media_next, media_previous

=== PRODUCTIVITY ===
calculate — do math (e.g. "2 + 2", "15 * 3.5", "2 ** 10")
translate — translate text between languages (free, no API key)
weather — get weather for any city (free, no API key)
clipboard_history — show current clipboard content

=== REMINDERS & TIMERS ===
set_reminder — set a reminder that fires after a duration (minutes, hours, seconds)
set_timer — set a countdown timer (use for 'timer for X seconds')
list_reminders — list all pending reminders and timers
cancel_reminder — cancel a reminder or timer by text or ID

=== AUTOMATION ===
add_automation — schedule a tool to run automatically on a schedule
list_automations — list all scheduled automations with status
remove_automation — remove an automation by ID or label
pause_automation — pause a specific automation
resume_automation — resume a paused automation
pause_all_automations — pause ALL automations at once
resume_all_automations — resume ALL automations at once

=== FEATURE TOGGLES ===
toggle_proactive_monitoring — turn system monitoring (battery, CPU) on/off
toggle_automation — pause/resume all scheduled automations at once
get_feature_status — check which background features are running

=== NOTES (knowledge base) ===
take_note — save a note with title and content (use for voice notes too!)
list_notes — list all saved notes
read_note — read a note by title
search_notes — search note contents for keywords
delete_note — delete a note

=== EMAIL ===
compose_email — open default email client with pre-filled draft (to, subject, body)

=== CODE ===
check_python_syntax — check a Python file for errors
run_project_tests — run the project's unit tests
format_python — format a Python file with Black

=== WEBSITES ===
serve_directory — start a local HTTP server to preview files in a directory
stop_server — stop a running local HTTP server by port
list_servers — list all active local HTTP servers
scaffold_website — create a basic HTML/CSS/JS website scaffold with optional frameworks

=== NETWORK & SERVERS ===
ping_host — ping a host to check if it's reachable
dns_lookup — look up DNS records (A, MX, NS, TXT, etc.)
check_port — check if a network port is open on a host
trace_route — trace the network route to a host
http_check — check if an HTTP/HTTPS server is responding

=== DOMAINS ===
check_domain — check if a domain name is available for registration
suggest_domains — suggest alternative domain names based on a keyword
domain_whois — get detailed WHOIS registration information

=== CREATE YOUR OWN TOOLS ===
create_tool — create a new custom tool at runtime (provide name, description, params, and Python source code with @tool decorator)
list_created_tools — list all tools that have been created dynamically
remove_created_tool — remove a previously created custom tool

=== LEARN FROM THE WEB ===
learn_from_web — research a topic from a web URL (or search the web) and save what you learn to the knowledge base
learn_from_reddit — fetch and save hot/trending Reddit posts to the knowledge base
learn_from_youtube — search YouTube for videos about a topic and save results
recall — search your memory for what you've learned about a topic
list_learned_topics — list everything you've learned so far, grouped by category
forget_topic — remove a learned topic from your learning index

=== PROJECT ANALYSIS ===
project_analyze — deep-scan any project directory and return a complete overview (language, deps, structure, tests, conventions, etc.) — use this to quickly understand a new project

=== USER PREFERENCES ===
save_preference — remember a user preference or convention (e.g. 'always use pnpm', 'tabs not spaces')
get_preferences — recall saved preferences, optionally filter by key or search term
remove_preference — delete a saved preference

=== DOCUMENTATION ===
update_documentation — update README, startup guide, changelog with current tool count and project state after making changes
get_documentation_status — check doc file status and tool count

=== GAMING ===
detect_gaming_setup — scan the system for installed gaming platforms and performance tools (Steam, Lutris, Heroic, Bottles, GameMode, MangoHud, Gamescope, GPU type, Proton versions)
list_games — list all installed games from Steam, Lutris, and Heroic Games Launcher
launch_game — launch a game by name with optional GameMode/Gamescope optimizations
configure_gaming — configure gaming performance (GameMode on/off, GPU power profile, hybrid graphics mode)
check_gaming_setup — comprehensive gaming health check with recommendations
install_gaming_tool — get installation instructions for gaming tools (gamemode, mangohud, gamescope, etc.)

=== UTILITY TOOLS ===
generate_password — generate a strong random password and copy to clipboard
pick_color — pick the color at your cursor position (returns hex + RGB)
set_alarm — set an alarm for a specific time (repeats until cancelled)
cancel_alarm — cancel a ringing alarm by label or ID
list_alarms — list all pending alarms
log_expense — log a spending entry with amount, category, description
query_expenses — query your expense history by period and category
export_expenses — export expense data as text table or CSV
organize_directory — organize files in a folder into categorized subfolders (dry-run by default)

=== LIFESTYLE ===
track_package — track a package by carrier (ups/fedex/usps/dhl) and tracking number
find_recipes — search for recipes by ingredients or dish name
start_weather_alerts — start proactive severe weather alerts for a location
stop_weather_alerts — stop the severe weather alerts

=== PDF TOOLKIT ===
pdf_merge — merge multiple PDF files into one
pdf_split — split a PDF into individual page files
pdf_extract_text — extract text from a PDF file

=== GIT ASSISTANT ===
git_status — show current git repo status with branch, changes, sync info
git_commit — stage all changes and commit with a message (shows diff preview first)
git_push — push committed changes to the remote repository
git_pull — pull the latest changes from the remote repository
git_log — show recent commit history

=== SHELL ===
run_shell — run any shell command (dangerous ones require confirmation)


=== CONTEXT AWARENESS ===
Before taking actions, use get_active_window to check what the user is doing:
- If they're in Firefox: use browser tools (browser_navigate, browser_click_link, etc.)
- If they're in the terminal: use system/file tools
- If they're elsewhere (code editor, settings, etc.): use the appropriate tools

For browser/media actions, always target Firefox directly using browser tools
and media tools. The tools handle focusing Firefox automatically.

=== SELF-IMPROVEMENT ===
You can create your own tools, learn from the web, and you automatically learn from conversations!

**Creating tools**: If you need a capability that doesn't exist as a tool, use 'create_tool' to write Python code for it. The code must import @tool from tools, define parameters, and handle errors. The tool becomes available immediately. Example:
  create_tool(name="slugify", description="Convert text to URL slug", params={"text": {"type": "string", "description": "text to slugify"}}, required=["text"], code="from tools import tool\n\n@tool(name='slugify', description='Convert text to a URL-friendly slug', params={'text': {'type': 'string', 'description': 'The text to slugify'}}, required=['text'])\ndef slugify(text: str) -> str:\n    import re\n    slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')\n    return slug")

**Learning from the web**: Use 'learn_from_web' to research topics and save what you learn. Use 'recall' to remember what you've learned before. This builds up over time — the more you learn, the smarter you get.

**Auto-learning from conversations**: Every time we discuss tech, coding, AI, or any useful topic, I automatically save the key information to my knowledge base. I detect when you're asking a research question, find the relevant topics, extract the meaty content, and save it for later. Research queries and tool results (web searches, documentation, etc.) are prioritized. The same topic won't be saved too often to avoid clutter. To see what I've learned, use 'recall' or 'list_learned_topics'.

**Important**: After creating a tool, use 'self_verify' to check that your code has no syntax errors and the tool functions properly.

=== REASONING (think like a senior engineer) ===
You have cognitive tools to help you work smarter:

**think(problem, context)** — Before complex multi-step tasks, call think() to step back and reason. Fill in the structured framework: Analysis → Options → Plan → Verification. This catches mistakes early.

**create_plan(name, steps)** — For tasks with 3+ steps, create a plan first. Track your progress with complete_step(). Use list_plans() to see what's left.

**run_command(command, what_to_check)** — Lightweight basher for safe verification: check syntax, test one-liners, list packages, run git status. Blocks dangerous operations (rm, sudo, curl, eval). For risky commands, use run_shell.

**self_review(files)** — After making changes, call self_review to check syntax, run tests, and get structured feedback. Fix any issues found.

**self_verify(files)** — Quick syntax + test check after edits.

**suggest_next_steps(context)** — When a task is done, suggest 2-3 specific followup actions the user could take next.

**list_plans()** — View all active plans with completion status.

Always use these tools in order: think → plan → implement → run_command/verify → review → suggest.

=== WORKFLOW ===
1. Check what window is active with get_active_window to understand context.
2. For browser tasks: use browser tools (they focus Firefox automatically).
3. For media (pause/play/skip): use media tools (they send keys to Firefox).
4. Take a screenshot (take_screenshot) to see the screen before clicking UI elements.
5. For math/translation/weather: use the calculate/translate/weather tools.
6. For saving info: use take_note to save notes to the knowledge base.
7. After completing actions, summarize concisely.
8. If you need a tool that doesn't exist, create it with create_tool and test it with self_verify or self_review.
9. To get smarter about a topic, use learn_from_web and recall later.
10. For complex tasks: think() → create_plan() → implement → complete_step() → self_review() → suggest_next_steps().

PERSONALITY: You are like JARVIS from Iron Man — confident, capable, loyal, and professional with a touch of warmth. You're direct and efficient, but not cold. You can be witty when appropriate. You address the user as "sir" or "boss" occasionally. Use varied responses instead of the same phrases.

VISION: When you call take_screenshot, a vision model analyzes the image and returns a detailed text description of what is on screen. Use this to locate buttons, text fields, menus, and other UI elements before interacting with them.

SAFETY: Destructive or potentially dangerous actions (deleting files, killing processes, risky shell commands, etc.) will be blocked pending user approval. Do not be surprised if such tool calls are rejected.

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
        self._automation_engine = None
        self._proactive_monitor = None
        self._load_skills()
        self._load_generated_tools()
        self._init_jarvis()
        self._init_automation()
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

        # Wire up tool references to engine instances
        import tools.reminder_tools, tools.feature_toggle, tools.automation_tools

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
                tools.feature_toggle.set_proactive_monitor(self._proactive_monitor)
            except Exception as exc:
                logger.debug("JARVIS proactive unavailable: %s", exc)

        # Wire reminder manager into tool layer
        if self._reminder_manager is not None:
            tools.reminder_tools.set_manager(self._reminder_manager)

        # Notification mirror
        if config.JARVIS_NOTIFICATION_MIRROR:
            try:
                from brain.notifications import NotificationMirror
                self._notify_mirror = NotificationMirror(speak_callback=self._jarvis_speak)
                self._notify_mirror.start()
                logger.info("JARVIS: Notification mirror enabled")
            except Exception as exc:
                logger.debug("JARVIS notification mirror unavailable: %s", exc)

    # ------------------------------------------------------------------
    # Automation engine initialization
    # ------------------------------------------------------------------

    def _init_automation(self) -> None:
        """Initialize the automation engine."""
        import tools.automation_tools, tools.feature_toggle
        from brain.automation import AutomationEngine

        # Callback that lets the automation engine execute tools
        def _execute_tool(name: str, params: dict) -> str:
            try:
                # Safety check — block dangerous tools from automations
                from safety.guard import SafetyGuard
                if SafetyGuard.requires_confirmation(name, params):
                    logger.warning("Automation blocked dangerous tool: %s(%s)", name, params)
                    return f"Blocked: {name} requires confirmation and cannot run in automation"
                func = tools.get_tool(name)
                return func(**params)
            except Exception as exc:
                logger.error("Automation tool %s failed: %s", name, exc)
                return f"Error: {exc}"

        self._automation_engine = AutomationEngine(tool_executor=_execute_tool)

        # Wire into tool layer
        tools.automation_tools.set_engine(self._automation_engine)
        tools.feature_toggle.set_automation_engine(self._automation_engine)

        # Start the engine
        self._automation_engine.start()

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

    def _load_generated_tools(self) -> None:
        """Load any previously created custom tools from tools/generated/."""
        try:
            loaded = tools.load_generated()
            if loaded:
                logger.info("Loaded %d generated tool(s): %s", len(loaded), ", ".join(loaded))
        except Exception as exc:
            logger.debug("No generated tools to load: %s", exc)

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
        return ask_confirmation(tool_name, params)

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
        print_tool(name, args)
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

        tool_results_content: list[str] = []

        for round_num in range(10):
            self._trim_history()
            message = self.client.chat(self.messages, tools=all_tools)
            self.messages.append(message)

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                self._maybe_autosave()

                # ── Auto-learn from this conversation turn ──
                response_content = message.get("content", "")
                try:
                    learned = auto_learn_from_response(user_text, response_content, tool_results_content or None)
                    if learned:
                        logger.info("Conversation auto-learn: %s", learned)
                except Exception as exc:
                    logger.debug("Auto-learn skipped: %s", exc)

                return response_content

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
                    tool_result_str = skill_result
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": tool_result_str,
                    })
                else:
                    tool_result_str = self._execute_with_confirmation(name, args)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": str(tool_result_str),
                    })

                tool_results_content.append(str(tool_result_str))

                # ── Auto-learn from tool results ──
                try:
                    learned = auto_learn_from_tool(name, args, str(tool_result_str))
                    if learned:
                        logger.info("Tool auto-learn: %s", learned)
                except Exception as exc:
                    logger.debug("Tool auto-learn skipped: %s", exc)

        self._maybe_autosave()

        response_content = message.get("content", "")
        try:
            learned = auto_learn_from_response(user_text, response_content, tool_results_content or None)
            if learned:
                logger.info("Conversation auto-learn: %s", learned)
        except Exception as exc:
            logger.debug("Auto-learn skipped: %s", exc)

        return response_content

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
            """Return the appropriate print helpers for the current mode.

            modern (default=True): clean, professional, minimal noise (default)
            freebuff (fb=True): super minimal, just text
            """
            if fb:
                return fb_print_user, fb_print_agent, fb_print_info, fb_print_error
            else:
                return print_user, print_agent, print_status, print_error

        try:
            while True:
                cmd_type, text = command_queue.get()
                p_user, p_agent, p_info, p_err = _set_helpers(freebuff)

                if cmd_type == "quit":
                    print_divider()
                    print_info("Goodbye!")
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
                        print_info("Goodbye!")
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
                                print_panel(result, title="Screenshot", style="cyan")
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
                                print_panel(info, title="System Status", style="cyan")
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
                            print_panel(direct_result, title="Action", style="cyan")
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
                show_thinking()
                response = self._chat_with_tools(user_text)
                hide_thinking()
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
        """Interactive text mode — pure keyboard input."""
        print_header("AILIEN", " — Text Mode")
        print_info("Type a command or 'quit' to exit.")
        print_info("/freebuff - minimal inline style  ·  /mute - toggle TTS")
        print_info("Need voice? Try: ./ailien --wake-word\n")
        # voice_enabled=False = no wake word detector (saves CPU)
        self._run_input_loop(start_freebuff=False, voice_enabled=False)

    def run_freebuff_mode(self) -> None:
        """Minimal inline terminal mode — no styling, just plain text."""
        print_header("AILIEN", " — Freebuff Mode")
        print_info("Minimal inline chat. /mute to toggle TTS, /fancy for rich mode.\n")
        # voice_enabled=False = no wake word detector (saves CPU)
        self._run_input_loop(start_freebuff=True, voice_enabled=False)

    def run_voice_mode(self) -> None:
        """Voice-interactive mode."""
        self._ensure_transcriber()
        self._set_status("idle")
        print_header("AILIEN", " — Voice Mode")
        print_info("Speak after the beep. Silence stops recording.")
        print_info("q - quit  ·  t - switch to text  ·  clear - reset\n")

        while True:
            try:
                prompt = console.input("  [dim]Press Enter to record, or type q/t/clear:[/dim] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print_info("Goodbye!")
                break

            if prompt == "q":
                print_info("Goodbye!")
                break
            if prompt == "t":
                self.run_text_mode()
                break
            if prompt == "clear":
                self._init_conversation()
                print_status("Conversation cleared.")
                continue

            # Record audio
            print_status("Recording... (speak now)")
            self._set_status("listening")
            audio = self.recorder.record_until_silence()
            self._set_status("thinking")
            if audio.size == 0:
                print_status("No audio detected.")
                self._set_status("idle")
                continue

            print_status("Transcribing...")
            text = self.transcriber.transcribe(audio)
            if not text:
                print_status("Could not understand audio.")
                self._set_status("idle")
                continue

            print_user(text)
            show_thinking()
            response = self._chat_with_tools(text)
            hide_thinking()
            print_agent(response)
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
        print_header("AILIEN", " — Wake Word Mode")
        print_info("Say 'Hey Jarvis' followed by your command.")
        print_info("sleep/wake/quit/screenshot/status/clear · volume/media/apps/keys")
        print_info("Press Ctrl+C to quit.\n")

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
        print_status("Listening for wake word...")

        def _handle_special_command(cmd: str) -> bool:
            """Check for voice control commands. Returns True if handled."""
            nonlocal _sleeping, _should_quit
            lower = cmd.lower().strip()

            # Sleep commands (detector keeps running so it can hear 'wake up')
            if lower in ("stop listening", "pause listening", "go to sleep", "sleep"):
                _sleeping = True
                print_status("Going to sleep. Say 'wake up' to resume.")
                speak("Going to sleep. Say wake up to resume.")
                return True

            # Wake commands
            if lower in ("start listening", "resume listening", "wake up", "wake"):
                if _sleeping:
                    _sleeping = False
                    print_status("Resumed listening.")
                    speak("I'm listening again.")
                else:
                    print_status("Already awake.")
                return True

            # Switch to text mode
            if lower in ("text mode", "switch to text", "keyboard mode"):
                print_status("Switching to text mode...")
                speak("Switching to text mode.")
                self.run_text_mode()
                return True

            # Quit commands
            if lower in ("quit", "exit", "goodbye", "shut down"):
                _should_quit = True
                print_status("Shutting down...")
                speak("Goodbye!")
                return True

            # Status command
            if lower in ("status", "system status", "computer status"):
                try:
                    info = tools.get_tool("system_info")()
                    print_panel(info, title="System Status", style="cyan")
                    speak("System status: " + " ".join(info.splitlines()))
                except Exception as exc:
                    print_error(f"System status failed: {exc}")
                    speak("Sorry, I couldn't get the system status.")
                return True

            # Screenshot command
            if lower in ("screenshot", "take screenshot", "capture screen"):
                try:
                    self._set_status("thinking")
                    result = tools.get_tool("take_screenshot")()
                    print_panel(result, title="Screenshot", style="cyan")
                    speak("Screenshot taken. " + " ".join(result.splitlines())[:200])
                except Exception as exc:
                    print_error(f"Screenshot failed: {exc}")
                    speak("Sorry, I couldn't take a screenshot.")
                return True

            # Clear conversation
            if lower in ("clear", "clear conversation", "reset"):
                self._init_conversation()
                print_status("Conversation cleared.")
                speak("Conversation cleared.")
                return True

            # Direct tool commands (volume, media, apps, etc.)
            direct_result = self._try_direct_voice_command(cmd)
            if direct_result is not None:
                print_panel(direct_result, title="Action", style="cyan")
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
                        print_status("Resumed listening.")
                        speak("I'm listening again.")
                    else:
                        pass
                    continue

                detector.pause()
                self._set_status("thinking")

                if not command:
                    # Wake word said without a command — record a follow-up
                    print_status("Wake word detected! Listening for command...")
                    try:
                        self._set_status("listening")
                        audio = self.recorder.record_until_silence()
                        self._set_status("thinking")
                    except RuntimeError:
                        print_error("Microphone unavailable.")
                        speak("Microphone unavailable.")
                        detector.resume()
                        self._set_status("listening")
                        continue
                    if audio.size == 0:
                        print_status("No audio detected. Try speaking louder.")
                        speak("I didn't hear anything. Please try again.")
                        detector.resume()
                        self._set_status("listening")
                        continue
                    print_status("Transcribing...")
                    command = self.transcriber.transcribe(audio)
                    if not command:
                        print_warning("Could not understand audio. Try again.")
                        speak("I didn't catch that. Please try again.")
                        detector.resume()
                        self._set_status("listening")
                        continue

                # Handle voice control commands first
                if _handle_special_command(command):
                    detector.resume()
                    if not _sleeping:
                        print_status("Listening for wake word...")
                        self._set_status("listening")
                    continue

                print_user(command)
                show_thinking()
                response = self._chat_with_tools(command)
                hide_thinking()
                print_agent(response)
                self._set_status("speaking")
                speak(response)
                print_status("Listening for wake word...")
                self._set_status("listening")
                detector.resume()
        except KeyboardInterrupt:
            print_info("Stopping wake word listener...")
        finally:
            detector.stop()
            print_info("Goodbye!")

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
        print_user(command)
        show_thinking()
        response = self._chat_with_tools(command)
        hide_thinking()
        print_agent(response)
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
        _print_banner()

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

    # Tray icon — only useful in daemon mode (background agent).
    # In terminal modes it just adds GLib noise for no benefit.
    tray = None
    if args.daemon:
        try:
            from gui.tray import TrayIcon
            tray = TrayIcon(overlay=overlay)
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
                print_info(f"Loaded conversation from {conv_path}")
        else:
            print_warning(f"Conversation file not found: {conv_path}")

    # Desktop toast notifications — only in daemon mode (no terminal to see)
    if args.daemon:
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
            if args.daemon:
                notify("AILIEN", "Agent stopped")
            # Stop background services
            if hasattr(agent, '_automation_engine') and agent._automation_engine:
                agent._automation_engine.stop()
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
