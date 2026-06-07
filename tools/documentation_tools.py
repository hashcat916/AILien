"""Documentation update tools — AILIEN can keep its own docs current.

After AILIEN makes any changes (new tools, config changes, bug fixes),
it should call update_documentation to keep the README, startup guide,
changelog, and setup.sh current.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from tools import tool

# Documentation files that can be updated
DOC_FILES = {
    "readme": "README.md",
    "startup": "ailien_startup.txt",
    "changelog": "knowledge/topics/changelog-june-7-2026.md",
    "setup": "setup.sh",
}

_PROJECT_DIR = Path(__file__).resolve().parent.parent


def _get_tool_stats() -> dict[str, Any]:
    """Scan the project and return current tool statistics.

    Discovers tools by scanning .py files for @tool decorators,
    which works even when tool modules haven't been imported yet.
    """
    categories: dict[str, list[str]] = {}
    tool_flat: list[str] = []

    # Scan all tool files for @tool decorators
    tools_dir = _PROJECT_DIR / "tools"
    for pyfile in sorted(tools_dir.rglob("*.py")):
        if pyfile.name.startswith("_"):
            continue
        if "generated" in str(pyfile):
            continue
        content = pyfile.read_text(encoding="utf-8", errors="replace")
        # Find @tool( decorators with name=...
        matches = re.findall(r'@tool\(\s*\n\s+name="([^"]+)"', content)
        if matches:
            cat_name = pyfile.stem.replace("_", " ").title()
            if cat_name.endswith("Tools"):
                cat_name = cat_name[:-6]
            elif cat_name.endswith("Tool"):
                cat_name = cat_name[:-5]
            for t in matches:
                categories.setdefault(cat_name, []).append(t)
                tool_flat.append(t)

    from datetime import datetime

    return {
        "total": len(tool_flat),
        "categories": categories,
        "tool_to_file": {},
        "all_tools": sorted(tool_flat),
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _update_readme(changes: str, stats: dict[str, Any]) -> str:
    """Generate updated README content with current tool listing."""
    return (
        "# AILIEN 👽🖥️\n\n"
        "Control your computer with voice or text using AILIEN — an AI assistant "
        "that can control your mouse, keyboard, browser, apps, files, screen, "
        "media, torrents, brightness, servers, domains, websites, and more.\n\n"
        f"_Last updated: {stats['last_updated']}_\n\n"
        "## What it does\n\n"
        "- **Voice control**: Speak commands (push-to-talk or wake-word \"Hey Jarvis\")\n"
        "- **Text control**: Type commands in an interactive chat\n"
        f"- **PC automation**: {stats['total']}+ tools — mouse, keyboard, screenshots, "
        "browser control, app launching, file management, shell commands, "
        "media playback, brightness control, torrent downloads, code verification, "
        "notes, email, reminders, timers, scheduled automation, system monitoring, "
        "server diagnostics, domain research, website scaffolding, tool creation, "
        "web learning\n"
        "- **Self-improving**: Can create its own tools at runtime and learn from the web\n"
        "- **Cloud-powered brain**: Uses xAI Grok (OpenAI-compatible API)\n"
        "- **Local speech**: Whisper runs locally — your voice never leaves your machine\n\n"
        "## Quick Start\n\n"
        "### 1. Get an API key\n\n"
        "**xAI (recommended)**: https://console.x.ai/ — sign up and copy your API key.\n\n"
        "### 2. Set your API key\n\n"
        "```bash\n"
        "# Option A: Environment variable\n"
        "export XAI_API_KEY=\"xai-...\"\n\n"
        "# Option B: .env file (auto-loaded)\n"
        "echo \"XAI_API_KEY=xai-...\" > .env\n"
        "```\n\n"
        "### 3. Install\n\n"
        "```bash\n"
        "chmod +x setup.sh && ./setup.sh\n"
        "```\n\n"
        "### 4. Run\n\n"
        "```bash\n"
        "cd ~/Desktop/my-project\n"
        "./ailien --text\n"
        "```\n\n"
        "## Modes\n\n"
        "| Command | Mode |\n"
        "|---------|------|\n"
        "| `./ailien --text` | Type commands in terminal |\n"
        "| `./ailien --gui` | GUI window with text + voice toggle |\n"
        "| `./ailien --voice` | Push-to-talk (press Enter, speak) |\n"
        "| `./ailien --wake-word` | Always listening — say \"Hey Jarvis\" |\n"
        "| `./ailien --freebuff` | Minimal inline terminal |\n"
        "| `./ailien --daemon` | Background tray icon |\n"
        "| `./ailien -c \"command\"` | Single command and exit |\n"
        "| `./ailien --serve` | HTTP API server (Open WebUI compatible) |\n\n"
        + _format_categories_section(stats) +
        "\n## Create Your Own Tools\n\n"
        "AILIEN can create new tools at runtime using `create_tool`:\n"
        "```\n"
        "create_tool(name=\"my_tool\", description=\"Does something\",\n"
        "  params='{\"arg\": {\"type\": \"string\"}}',\n"
        "  required='[\"arg\"]',\n"
        "  code=\"from tools import tool\\n...\")\n"
        "```\n"
        "The tool is validated (syntax + safety), saved to `tools/generated/`, "
        "and registered immediately — no restart needed.\n\n"
        "## Learn From the Web\n\n"
        "AILIEN can research topics and remember them:\n"
        "- `learn_from_web` — fetch a URL or search the web, extract content, save to knowledge base\n"
        "- `learn_from_reddit` — save hot posts from any subreddit\n"
        "- `learn_from_youtube` — search and save video results\n"
        "- `recall` — search your memory for previously learned topics\n"
        "- `list_learned_topics` — see everything you've learned\n\n"
        "## Safety\n\n"
        "- **User confirmation** required for destructive actions (delete, kill, risky shell)\n"
        "- **Blocks** obviously dangerous commands (`rm -rf /`, `mkfs`, etc.)\n"
        "- **Prevents path traversal** in file operations\n"
        "- **Blocks** reading sensitive system files (`/etc/shadow`, `/proc`, etc.)\n"
        "- **Automation engine** blocks dangerous tools from running on schedules\n"
        "- **Tool creation** validates generated code — blocks dangerous imports and patterns\n\n"
        "## Project Structure\n\n"
        "```\n"
        ".\n"
        "├── main.py                   # Entry point, agent loop, system prompt\n"
        "├── config.py                 # Settings (env vars, API keys, defaults)\n"
        "├── ailien                    # Launcher script (activates venv)\n"
        "├── setup.sh                  # One-command setup\n"
        "├── requirements.txt          # Python dependencies\n"
        "├── .env                      # API keys (you create this)\n"
        "│\n"
        "├── tools/                    # Tool functions\n"
        "│   ├── __init__.py           # Tool registry + @tool decorator\n"
        "│   ├── generated/            # User/AI-created tools (runtime)\n"
        "│   ├── mouse.py, keyboard.py, screen.py\n"
        "│   ├── apps.py, files.py, shell.py, system.py\n"
        "│   ├── browser.py, browser_extras.py\n"
        "│   ├── website_tools.py, server_tools.py, domain_tools.py\n"
        "│   ├── display_tools.py, media_tools.py, torrent_tools.py\n"
        "│   ├── productivity.py, code_tools.py, notes.py\n"
        "│   ├── email_tool.py, reminder_tools.py\n"
        "│   ├── automation_tools.py, feature_toggle.py\n"
        "│   ├── create_tool.py, learn_tools.py\n"
        "│   └── documentation_tools.py\n"
        "│\n"
        "├── brain/                    # Background engines\n"
        "│   ├── reminders.py          # Reminder/timer manager (persistent)\n"
        "│   ├── proactive.py          # System health monitor\n"
        "│   ├── automation.py         # Scheduled task engine\n"
        "│   ├── quick_answers.py      # Instant responses\n"
        "│   ├── youtube.py, reddit.py # Content fetchers\n"
        "│   ├── notifications.py      # Desktop notification mirror\n"
        "│   ├── knowledge.py          # Note/knowledge base\n"
        "│   ├── toolmaker.py          # Self-tool-creation engine\n"
        "│   └── learner.py            # Web learning engine\n"
        "│\n"
        "├── audio/                    # Recording, transcription, wake word\n"
        "├── gui/                      # VoiceWindow, overlay, tray icon\n"
        "├── llm/                      # API client\n"
        "├── safety/                   # Safety guard & confirmations\n"
        "├── skills/                   # User-defined skill plugins\n"
        "├── conversations/            # Saved chat history\n"
        "├── wake_words/               # Custom wake word models\n"
        "└── .cache/                   # Logs, automations, reminders, learner\n"
        "```\n\n"
        "## Configuration\n\n"
        "Set via environment variables or `.env` file:\n\n"
        "| Variable | Default | Description |\n"
        "|----------|---------|-------------|\n"
        "| `XAI_API_KEY` | *(required)* | xAI API key |\n"
        "| `CLOUD_MODEL` | `grok-4.3` | LLM model for reasoning + tool calling |\n"
        "| `CLOUD_BASE_URL` | `https://api.x.ai/v1` | API endpoint |\n"
        "| `VISION_MODEL` | `grok-4.3` | Vision model for screenshot analysis |\n"
        "| `WHISPER_MODEL` | `tiny` | Whisper size |\n"
        "| `TTS_ENGINE` | `pyttsx3` | `pyttsx3` (offline) or `edge` (natural) |\n"
        "| `JARVIS_REMINDERS` | `true` | Enable reminder/timer system |\n"
        "| `JARVIS_PROACTIVE` | `true` | Enable battery/CPU monitoring |\n"
        "| `JARVIS_QUICK_ANSWERS` | `true` | Enable instant responses |\n"
        "| `CONVERSATION_AUTO_SAVE` | `true` | Auto-save chat history |\n"
        "| `SKILLS_ENABLED` | `true` | Enable skill plugins |\n"
        "| `AGENT_VOICE_FEEDBACK` | `true` | Text-to-speech on/off |\n"
        "| `WAKE_WORD_CHUNK_MAX_DURATION` | `1.0` | Max seconds per audio chunk |\n"
        "| `LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING |\n\n"
        "## Environment Variables Quick Reference\n\n"
        "```bash\n"
        "# Required: at least one API key\n"
        "export XAI_API_KEY=\"xai-...\"\n\n"
        "# Optional overrides\n"
        "export CLOUD_MODEL=\"grok-4.3\"\n"
        "export WHISPER_MODEL=\"tiny\"\n"
        "export TTS_ENGINE=\"pyttsx3\"\n"
        "export JARVIS_PROACTIVE=\"true\"\n"
        "export JARVIS_REMINDERS=\"true\"\n"
        "export AGENT_VOICE_FEEDBACK=\"true\"\n"
        "export CONVERSATION_AUTO_SAVE=\"true\"\n"
        "```\n\n"
        "## Custom Wake Words\n\n"
        "Add to `.env` to customize wake phrases:\n"
        "```env\n"
        "AGENT_WAKE_WORDS=hey alan, what's up alan, hello alan\n"
        "```\n\n"
        "For Picovoice Porcupine (offline), see `wake_words/README.md`.\n\n"
        "## Known Limitations\n\n"
        "- **Wayland**: Window detection requires X11. `get_active_window` needs `xdotool`.\n"
        "- **Transmission**: Torrent tools need `transmission-cli` + `transmission-daemon`.\n"
        "- **Internet required**: The brain runs in the cloud.\n"
        "- **Linux**: Tested on Ubuntu/Debian. Some features need X11.\n\n"
        "## License\n\n"
        "MIT\n"
    )


def _format_categories_section(stats: dict[str, Any]) -> str:
    """Format the tools listing section for README."""
    lines = [f"## All {stats['total']} Tools\n"]
    category_order = [
        "Mouse", "Keyboard", "Screen", "Apps", "Files", "System",
        "Window", "Browser", "Browser Extras", "Media", "Local Media",
        "Display", "Torrents", "Productivity", "Reminder", "Automation",
        "Feature Toggle", "Notes", "Email", "Code", "Website", "Server",
        "Domain", "Gaming", "Create Tool", "Reasoning", "Agent Browser",
        "Course", "Learn", "Project", "Utility", "Lifestyle", "Documentation",
        "Shell",
    ]

    cat_map = stats.get("categories", {})
    seen = set()
    for cat_name in category_order:
        for actual_cat in cat_map:
            if actual_cat.lower().startswith(cat_name.lower()):
                tools_list = cat_map[actual_cat]
                lines.append(f"### {actual_cat}\n")
                for t in tools_list:
                    if t not in seen:
                        lines.append(f"  `{t}`")
                        seen.add(t)
                lines.append("")

    # Any uncategorized
    remaining = [t for t in stats.get("all_tools", []) if t not in seen]
    if remaining:
        lines.append("### Other\n")
        for t in remaining:
            lines.append(f"  `{t}`")
        lines.append("")

    return "\n".join(lines)


def _update_changelog(changes: str, stats: dict[str, Any]) -> str:
    """Append a new changelog entry, preserving existing history."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = stats["total"]

    # Read existing changelog
    changelog_path = _PROJECT_DIR / "knowledge" / "topics" / "changelog-june-7-2026.md"
    existing = ""
    if changelog_path.exists():
        content = changelog_path.read_text(encoding="utf-8")
        # Skip the title line if it exists
        lines = content.split("\n")
        if lines and lines[0].startswith("# "):
            existing = "\n".join(lines[1:]).strip()

    new_entry = (
        f"\n---\n\n## Update — {now}\n\n"
        f"{changes}\n\n"
        f"**Current status**: {total} tools, {len(stats['categories'])} categories"
    )

    return (
        f"# AILIEN Changelog\n\n"
        f"_{now}_\n\n"
        f"{new_entry}\n\n"
        f"---\n"
        f"{existing}"
    )


def _update_startup_guide(stats: dict[str, Any]) -> str:
    """Generate updated startup guide content."""
    total = stats["total"]
    categories = stats.get("categories", {})
    all_tools = stats.get("all_tools", [])

    # Build category lines from the stats
    cat_lines = []
    for cat_name in sorted(categories.keys()):
        tools_sorted = sorted(categories[cat_name])
        cat_desc = ", ".join(tools_sorted[:6])
        if len(tools_sorted) > 6:
            cat_desc += f" (+{len(tools_sorted) - 6} more)"
        cat_lines.append(f"  {cat_name:10s}  {cat_desc}")

    return (
        "╔══════════════════════════════════════════════════════════════════╗\n"
        "║              AILIEN — Startup Commands                          ║\n"
        "║              AI computer control assistant                      ║\n"
        f"║              {total} tools · voice & text · automation · self-improving    ║\n"
        "╚══════════════════════════════════════════════════════════════════╝\n"
        "\n"
        "Project: /home/alan/Desktop/my-project\n"
        "Launcher: ./ailien\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "ALL MODES\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  ./ailien --text          — Chat by typing\n"
        "  ./ailien --voice         — Push-to-talk voice\n"
        "  ./ailien --wake-word     — Always listening (say \"hey jarvis\")\n"
        "  ./ailien --gui            — GUI window with voice toggle\n"
        "  ./ailien --freebuff       — Minimal inline mode\n"
        "  ./ailien --daemon         — Background tray icon\n"
        "  ./ailien --serve          — HTTP API server\n"
        "  ./ailien -c \"command\"    — Single command, then exit\n"
        "  ./ailien --list-conversations   — List saved chats\n"
        "  ./ailien --conversation conv.json  — Load a conversation\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "TEXT MODE COMMANDS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  quit / exit / q        — Stop the agent\n"
        "  clear                  — Reset conversation\n"
        "  /freebuff              — Minimal inline output\n"
        "  /fancy                 — Rich panel output\n"
        "  /mute /voice           — Toggle TTS\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "VOICE CONTROLS (wake-word mode)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  Activation phrases (22 total):\n"
        "    hey ailien, ok ailien, ailien, hey alien, ok alien, alien,\n"
        "    hey jarvis, ok jarvis, jarvis,\n"
        "    hello, hey, hi, hello there, hey there, hi there,\n"
        "    what's up, sup, yo, howdy,\n"
        "    good morning, good afternoon, good evening\n"
        "\n"
        "  Voice commands:\n"
        "    \"screenshot\"       — Take a screenshot\n"
        "    \"status\"           — Show system status\n"
        "    \"go to sleep\"      — Pause listening (\"wake up\" to resume)\n"
        "    \"quit\"             — Shut down\n"
        "    \"volume up/down\"   — Adjust volume\n"
        "    \"mute/unmute\"      — Toggle audio\n"
        "    \"play/pause/next\"  — Media controls (YouTube, etc.)\n"
        "    \"open firefox\"     — Launch an app\n"
        "    \"focus terminal\"   — Switch to a window\n"
        "    \"minimize window\"  — Window management\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "CREATE YOUR OWN TOOLS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  AILIEN can create new tools at runtime:\n"
        "    \"create a tool that converts text to a URL slug\"\n"
        "    \"list created tools\"\n"
        "    \"remove the slugify tool\"\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "LEARN FROM THE WEB\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  AILIEN researches topics and remembers them:\n"
        "    \"learn about Python async from the web\"\n"
        "    \"learn from reddit r/MachineLearning\"\n"
        "    \"recall what you know about async\"\n"
        "    \"list what you've learned\"\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "REMINDERS & TIMERS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  \"remind me in 10 minutes to check the oven\"\n"
        "  \"set a timer for 3 minutes\"\n"
        "  \"list my reminders\"\n"
        "  \"cancel the timer\"\n"
        "  \"remind me every day at 9am to take vitamins\" (via automation)\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "AUTOMATION (scheduled tasks)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  \"check the weather every hour\"\n"
        "  \"tell me the system status every 30 minutes\"\n"
        "  \"list my automations\"\n"
        "  \"pause the weather check\"\n"
        "  \"pause all automations\"\n"
        "  \"turn off proactive monitoring\"\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"TOOL CATEGORIES ({total} total)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n" +
        "\n".join(cat_lines) +
        "\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "NETWORK & DOMAIN TOOLS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  ping_host     — Ping any host\n"
        "  dns_lookup    — DNS records (A, MX, NS, TXT)\n"
        "  check_port    — Check if a port is open\n"
        "  trace_route   — Trace network path\n"
        "  http_check    — Check if HTTP server is responding\n"
        "  check_domain  — Check domain availability\n"
        "  domain_whois  — Get WHOIS registration details\n"
        "  suggest_domains — Suggest domain name variations\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "WEBSITE TOOLS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  serve_directory   — Start a local HTTP server\n"
        "  stop_server       — Stop a running server\n"
        "  list_servers      — List active servers\n"
        "  scaffold_website  — Create HTML/CSS/JS scaffold\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "DESKTOP SHORTCUTS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  AILIEN.desktop           → Daemon mode (double-click to launch)\n"
        "  AILIEN-Text.desktop      → Text chat (opens terminal)\n"
        "  AILIEN-Voice.desktop     → Voice mode (opens terminal)\n"
        "  AILIEN-Server.desktop    → HTTP API (opens terminal)\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "CUSTOM ACTIVATION PHRASES\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  Add to .env:\n"
        "    AGENT_WAKE_WORDS=hey alan, what's up alan, hello alan\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "RE-RUN SETUP (if needed)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "  cd ~/Desktop/my-project && ./setup.sh\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )


def _safe_write(filepath: Path, content: str) -> str:
    """Safely write content to a documentation file.

    Only allows writing to known doc files within the project directory.
    """
    # Resolve to an absolute path
    try:
        target = (filepath if filepath.is_absolute() else _PROJECT_DIR / filepath).resolve()
    except Exception as e:
        return f"Invalid path: {e}"

    # Verify it's within the project directory
    try:
        target.relative_to(_PROJECT_DIR)
    except ValueError:
        return f"Access denied: {target} is outside the project directory."

    # Verify it's a known doc file or in the knowledge directory
    allowed_prefixes = [
        _PROJECT_DIR / "README.md",
        _PROJECT_DIR / "ailien_startup.txt",
        _PROJECT_DIR / "setup.sh",
        _PROJECT_DIR / "knowledge",
    ]
    is_allowed = False
    for prefix in allowed_prefixes:
        try:
            target.relative_to(prefix)
            is_allowed = True
            break
        except ValueError:
            continue

    if not is_allowed:
        return f"Access denied: {target} is not a documentation file."

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel_path = target.relative_to(_PROJECT_DIR)
        return f"Updated: {rel_path}"
    except Exception as e:
        return f"Failed to write {target}: {e}"


@tool(
    name="update_documentation",
    description="Update AILIEN's documentation files (README, startup guide, changelog, etc.) to reflect the current state after changes. Call this after creating tools, modifying config, or any other changes.",
    params={
        "changes": {
            "type": "string",
            "description": "Description of what changed. Be specific (e.g. 'Added 2 new tools: weather and translate. Fixed bug in skills loader.'). This goes in the changelog.",
        },
        "files": {
            "type": "string",
            "description": "Comma-separated list of files to update: 'readme', 'startup', 'changelog', or 'all' (default: all)",
            "default": "all",
        },
    },
    required=["changes"],
)
def update_documentation(changes: str, files: str = "all") -> str:
    """Update documentation files to reflect current project state.

    Call this after making changes to keep docs in sync.
    """
    stats = _get_tool_stats()
    results = []

    files_to_update = [f.strip().lower() for f in files.split(",")]

    if "all" in files_to_update or "readme" in files_to_update:
        content = _update_readme(changes, stats)
        result = _safe_write(_PROJECT_DIR / "README.md", content)
        results.append(result)

    if "all" in files_to_update or "startup" in files_to_update:
        content = _update_startup_guide(stats)
        result = _safe_write(_PROJECT_DIR / "ailien_startup.txt", content)
        results.append(result)

    if "all" in files_to_update or "changelog" in files_to_update:
        content = _update_changelog(changes, stats)
        result = _safe_write(
            _PROJECT_DIR / "knowledge" / "topics" / "changelog-june-7-2026.md",
            content,
        )
        results.append(result)

    return "\n".join(results)


@tool(
    name="get_documentation_status",
    description="Check the current documentation status: tool count, which doc files exist, and when they were last updated.",
    params={},
    required=[],
)
def get_documentation_status() -> str:
    """Check the current status of all documentation files."""
    stats = _get_tool_stats()
    lines = [
        f"📊 Project Status:",
        f"   {stats['total']} tools registered",
        f"   {len(stats['categories'])} categories",
        f"\n📄 Documentation Files:",
    ]

    for name, rel_path in DOC_FILES.items():
        full_path = _PROJECT_DIR / rel_path
        if full_path.exists():
            size = full_path.stat().st_size
            mtime = datetime.fromtimestamp(full_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            lines.append(f"   ✅ {rel_path}  ({size} bytes, updated {mtime})")
        else:
            lines.append(f"   ❌ {rel_path}  (missing)")

    lines.append(f"\n🛠️  Last updated by docs tool: {stats['last_updated']}")
    return "\n".join(lines)
