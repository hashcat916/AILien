<div align="center">
  <img src="icons/ailien_logo.png" alt="AILIEN" width="120" />

  # AILIEN 👽

  **AI-Powered Desktop Assistant — Voice & Text Computer Control**

  <p align="center">
    <a href="#-features"><img src="https://img.shields.io/badge/157%2B-Tools-brightgreen?style=flat-square" alt="Tools" /></a>
    <a href="#-quick-start"><img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python" alt="Python" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License" /></a>
    <a href="https://github.com/hashcat916/AILien"><img src="https://img.shields.io/badge/Platform-Linux-important?style=flat-square&logo=linux" alt="Platform" /></a>
    <a href="https://console.x.ai"><img src="https://img.shields.io/badge/Powered%20by-xAI%20Grok-black?style=flat-square" alt="xAI" /></a>
    <br />
    <a href="#-modes"><img src="https://img.shields.io/badge/🎤%20Voice%20Control-On-success?style=flat-square" alt="Voice" /></a>
    <a href="#-modes"><img src="https://img.shields.io/badge/⌨️%20Text%20Mode-On-success?style=flat-square" alt="Text" /></a>
    <a href="#-modes"><img src="https://img.shields.io/badge/🤖%20Self--Improving-On-success?style=flat-square" alt="Self-improving" /></a>
  </p>

  <p align="center">
    <b>English</b> ·
    <a href="#-quick-start">Quick Start</a> ·
    <a href="#-features">Features</a> ·
    <a href="#-project-structure">Structure</a> ·
    <a href="#-create-your-own-tools">Extend</a>
  </p>
</div>

---

## 📋 Overview

**AILIEN** is an AI assistant that lives on your desktop and controls your computer through voice or text commands. Powered by **xAI Grok**, it uses **157+ tools** to control your mouse, keyboard, browser, apps, files, media, system settings, and more — all while keeping your voice data local with on-device Whisper transcription.

> 🚀 **Run** — `./ailien --text`
> 🎤 **Speak** — `./ailien --wake-word`
> 🖥️ **GUI** — `./ailien --gui`

---

## ✨ Features

<table>
<tr>
  <td width="50%">
    <h3>🎤 Voice & Text Control</h3>
    <ul>
      <li><b>Wake word</b> — "Hey Jarvis" (always listening mode)</li>
      <li><b>Push-to-talk</b> — Press Enter, speak, release</li>
      <li><b>Text chat</b> — Type commands interactively</li>
      <li><b>GUI window</b> — Full UI with voice toggle</li>
      <li><b>HTTP API</b> — Open WebUI compatible server</li>
    </ul>
  </td>
  <td width="50%">
    <h3>🖱️ Desktop Control</h3>
    <ul>
      <li>Mouse movement, clicks, scrolling, dragging</li>
      <li>Keyboard typing, shortcuts, clipboard</li>
      <li>Screenshot capture & screen OCR</li>
      <li>Application launching & process management</li>
      <li>File system navigation & management</li>
    </ul>
  </td>
</tr>
<tr>
  <td width="50%">
    <h3>🌐 Browser & Web</h3>
    <ul>
      <li>Navigate, search, click links, fill forms</li>
      <li>Multiple tabs, back/forward, refresh</li>
      <li>Web scraping via <code>get_webpage_text</code></li>
      <li>Local HTTP server & website scaffolding</li>
      <li>Domain research (WHOIS, DNS, availability)</li>
    </ul>
  </td>
  <td width="50%">
    <h3>🧠 Self-Improving</h3>
    <ul>
      <li>Creates new tools <b>at runtime</b> — no restart needed</li>
      <li>Learns from the web, Reddit, YouTube</li>
      <li>Auto-learns from conversations</li>
      <li>Knowledge base with recall</li>
      <li>Scheduled automations & reminders</li>
    </ul>
  </td>
</tr>
<tr>
  <td width="50%">
    <h3>🎮 Media & Gaming</h3>
    <ul>
      <li>Local music/video search & playback</li>
      <li>Browser media play/pause/skip</li>
      <li>Torrent downloads via Transmission</li>
      <li>Game detection (Steam, Lutris, Heroic)</li>
      <li>GameMode/MangoHud/Gamescope integration</li>
    </ul>
  </td>
  <td width="50%">
    <h3>🔧 Developer Tools</h3>
    <ul>
      <li>Python syntax checking & formatting (Black)</li>
      <li>Pytest integration</li>
      <li>Git status, commit, push, pull, log</li>
      <li>PDF merge/split/extract</li>
      <li>Project analysis & preference saving</li>
    </ul>
  </td>
</tr>
</table>

---

## 🚀 Quick Start

### 1. Get an API Key

| Provider | URL |
|----------|-----|
| **xAI** (recommended) | [console.x.ai](https://console.x.ai/) |

### 2. Set Your API Key

```bash
# Environment variable
export XAI_API_KEY="xai-..."

# Or .env file (auto-loaded)
echo "XAI_API_KEY=xai-..." > .env
```

### 3. Install

```bash
chmod +x setup.sh && ./setup.sh
```

### 4. Run

```bash
# Text mode (recommended to start)
./ailien --text

# Or with wake word ("Hey Jarvis")
./ailien --wake-word

# Or GUI window
./ailien --gui
```

---

## 🎯 Modes

| Command | Mode | Description |
|---------|------|-------------|
| `./ailien --text` | 💬 Text | Interactive chat in terminal |
| `./ailien --gui` | 🖥️ GUI | Voice window with start/pause/stop |
| `./ailien --voice` | 🎤 Push-to-talk | Press Enter, speak, release |
| `./ailien --wake-word` | 👂 Always-on | Say "Hey Jarvis" + command |
| `./ailien --freebuff` | 📝 Minimal | Clean inline text mode |
| `./ailien --daemon` | 🔄 Background | Tray icon + wake word |
| `./ailien -c "command"` | ⚡ One-shot | Single command, then exit |
| `./ailien --serve` | 🌐 API Server | Open WebUI compatible |

---

## 🔧 Configuration

Set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `XAI_API_KEY` | *(required)* | xAI API key for LLM & vision |
| `CLOUD_MODEL` | `grok-4.3` | LLM model for reasoning + tool calling |
| `CLOUD_BASE_URL` | `https://api.x.ai/v1` | API endpoint |
| `VISION_MODEL` | `grok-4.3` | Vision model for screenshot analysis |
| `WHISPER_MODEL` | `tiny` | Whisper model size (tiny/base/small/medium/large) |
| `TTS_ENGINE` | `pyttsx3` | Text-to-speech: `pyttsx3` (offline) or `edge` (natural) |
| `JARVIS_REMINDERS` | `true` | Enable reminder/timer system |
| `JARVIS_PROACTIVE` | `true` | Enable battery/CPU monitoring |
| `JARVIS_QUICK_ANSWERS` | `true` | Enable instant responses |
| `CONVERSATION_AUTO_SAVE` | `true` | Auto-save chat history |
| `SKILLS_ENABLED` | `true` | Enable skill plugins |
| `AGENT_VOICE_FEEDBACK` | `true` | Text-to-speech on/off |
| `LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING |

### Custom Wake Words

```env
# In .env file
AGENT_WAKE_WORDS=hey alan, what's up alan, hello alan
```

---

## 📦 All 157 Tools

<details>
<summary><b>🖱️ Mouse</b> (5 tools)</summary>

- `mouse_move` — Move cursor to coordinates
- `mouse_click` — Click at current or specified position
- `mouse_scroll` — Scroll up/down
- `mouse_drag` — Drag from one point to another
- `get_mouse_position` — Get current cursor coordinates
</details>

<details>
<summary><b>⌨️ Keyboard</b> (4 tools)</summary>

- `type_text` — Type text at current cursor position
- `press_key` — Press a key or key combination
- `clipboard_get` — Read clipboard contents
- `clipboard_set` — Set clipboard contents
</details>

<details>
<summary><b>🖥️ Screen</b> (2 tools)</summary>

- `take_screenshot` — Capture screen to image
- `read_screen_text` — OCR from screenshot
</details>

<details>
<summary><b>📂 Apps & Files</b> (8 tools)</summary>

- `launch_app`, `list_running_apps`, `kill_process`, `find_process`
- `list_directory`, `read_file`, `find_file`, `open_file`
</details>

<details>
<summary><b>🌐 Browser</b> (16 tools)</summary>

- Navigation: `open_url`, `browser_navigate`, `browser_go_back`, `browser_go_forward`, `browser_refresh`
- Tabs: `browser_new_tab`, `browser_close_tab`, `browser_switch_tab`
- Interaction: `browser_click_link`, `browser_fill_form`, `browser_search`, `browser_find`, `browser_scroll`
- Info: `browser_get_info`, `get_webpage_text`
</details>

<details>
<summary><b>🔊 System & Media</b> (15 tools)</summary>

- `system_info`, `get_active_window`
- Volume: `set_volume`, `volume_up`, `volume_down`, `mute_volume`, `unmute_volume`
- Window: `minimize_window`, `maximize_window`, `restore_window`, `focus_window`
- Media: `media_play_pause`, `media_next`, `media_previous`, `play_media`, `list_media`
</details>

<details>
<summary><b>🖼️ Display</b> (4 tools)</summary>

- `set_brightness`, `brightness_up`, `brightness_down`, `get_brightness`
</details>

<details>
<summary><b>🧮 Productivity</b> (4 tools)</summary>

- `calculate`, `translate`, `weather`, `clipboard_history`
</details>

<details>
<summary><b>⏰ Reminders & Automation</b> (12 tools)</summary>

- `set_reminder`, `set_timer`, `list_reminders`, `cancel_reminder`
- `add_automation`, `list_automations`, `remove_automation`, `pause_automation`, `resume_automation`
- `pause_all_automations`, `resume_all_automations`
- Toggle: `toggle_proactive_monitoring`, `toggle_automation`, `get_feature_status`
</details>

<details>
<summary><b>📝 Notes & Email</b> (6 tools)</summary>

- `take_note`, `list_notes`, `read_note`, `search_notes`, `delete_note`
- `compose_email`
</details>

<details>
<summary><b>💻 Code & Git</b> (12 tools)</summary>

- `check_python_syntax`, `run_project_tests`, `format_python`, `self_verify`
- `git_status`, `git_commit`, `git_push`, `git_pull`, `git_log`
</details>

<details>
<summary><b>🌍 Web & Network</b> (12 tools)</summary>

- Server: `serve_directory`, `stop_server`, `list_servers`, `scaffold_website`
- Network: `ping_host`, `dns_lookup`, `check_port`, `trace_route`, `http_check`
- Domains: `check_domain`, `domain_whois`, `suggest_domains`
</details>

<details>
<summary><b>🎮 Gaming</b> (6 tools)</summary>

- `detect_gaming_setup`, `list_games`, `launch_game`, `configure_gaming`, `check_gaming_setup`, `install_gaming_tool`
</details>

<details>
<summary><b>🧠 Reasoning & Learning</b> (16 tools)</summary>

- Reasoning: `think`, `create_plan`, `list_plans`, `complete_step`, `self_review`, `run_command`, `suggest_next_steps`
- Learning: `learn_from_web`, `learn_from_reddit`, `learn_from_youtube`, `recall`, `list_learned_topics`, `forget_topic`
- Agent Browser: `search_capabilities`, `install_capability`, `list_available_capabilities`, `find_missing_capability`
- Courses: `build_course`, `generate_book`, `list_courses`, `read_lesson`, `find_tutorials`
</details>

<details>
<summary><b>🔧 Utility & Lifestyle</b> (16 tools)</summary>

- Utility: `generate_password`, `pick_color`, `set_alarm`, `cancel_alarm`, `list_alarms`, `log_expense`, `query_expenses`, `export_expenses`, `organize_directory`
- Lifestyle: `track_package`, `find_recipes`, `start_weather_alerts`, `stop_weather_alerts`
- PDF: `pdf_merge`, `pdf_split`, `pdf_extract_text`
</details>

<details>
<summary><b>🛠️ Other</b> (6 tools)</summary>

- `create_tool`, `list_created_tools`, `remove_created_tool`
- `add_torrent`, `torrent_status`, `torrent_pause`, `torrent_resume`
- `update_documentation`, `get_documentation_status`
- `save_preference`, `get_preferences`, `remove_preference`, `project_analyze`
- `run_shell`
</details>

---

## 🧠 Create Your Own Tools

AILIEN can create new tools at runtime — no coding experience needed:

```bash
create_tool(
  name="my_tool",
  description="Does something useful",
  params='{"arg": {"type": "string", "description": "An argument"}}',
  required='["arg"]',
  code="from tools import tool\\n\\n@tool(...)\\ndef my_tool(arg: str) -> str:\\n    return f'Hello {arg}'"
)
```

The tool is validated (syntax + safety), saved to `tools/generated/`, and registered immediately — **no restart required**.

---

## 🔒 Safety

| Layer | Protection |
|-------|-----------|
| **User confirmation** | Required for destructive actions (delete, kill, risky shell) |
| **Command blocking** | Blocks dangerous commands (`rm -rf /`, `mkfs`, etc.) |
| **Path traversal** | Prevents reading/writing outside allowed paths |
| **Sensitive files** | Blocks `/etc/shadow`, `/proc`, and other system files |
| **Automation guard** | Dangerous tools blocked from running on schedules |
| **Code validation** | Tool creation checks for dangerous imports & patterns |

---

## 📁 Project Structure

```
ailien/
├── main.py                     # Entry point, agent loop, system prompt
├── config.py                   # Settings, env vars, API keys, defaults
├── ailien                      # Launcher script (activates venv)
├── setup.sh                    # One-command setup
├── requirements.txt            # Python dependencies
├── .env                        # API keys (you create this)
├── LICENSE                     # MIT license
│
├── tools/                      # Tool functions (157+)
│   ├── __init__.py             # Tool registry + @tool decorator
│   ├── generated/              # User/AI-created tools (runtime)
│   ├── mouse.py, keyboard.py, screen.py
│   ├── apps.py, files.py, shell.py, system.py
│   ├── browser.py, browser_extras.py
│   ├── website_tools.py, server_tools.py, domain_tools.py
│   ├── display_tools.py, media_tools.py, torrent_tools.py
│   ├── productivity.py, code_tools.py, notes.py
│   ├── email_tool.py, reminder_tools.py
│   ├── automation_tools.py, feature_toggle.py
│   ├── create_tool.py, learn_tools.py
│   └── documentation_tools.py
│
├── brain/                      # Background intelligence engines
│   ├── reminders.py            # Reminder/timer manager (persistent)
│   ├── proactive.py            # System health monitor
│   ├── automation.py           # Scheduled task engine
│   ├── quick_answers.py        # Instant responses
│   ├── youtube.py, reddit.py   # Content fetchers
│   ├── notifications.py        # Desktop notification mirror
│   ├── knowledge.py            # Note/knowledge base
│   ├── toolmaker.py            # Self-tool-creation engine
│   ├── learner.py              # Web learning engine
│   └── conversation_learner.py # Automatic conversation learning
│
├── audio/                      # Recording, transcription, wake word
├── gui/                        # VoiceWindow, overlay, tray icon
├── llm/                        # Cloud API client
├── safety/                     # Safety guard & confirmations
├── skills/                     # User-defined skill plugins
├── conversations/              # Saved chat history
├── wake_words/                 # Custom wake word models
├── icons/                      # App icons & logos
└── .cache/                     # Logs, automations, reminders
```

---

## 💡 Known Limitations

| Limitation | Details |
|------------|---------|
| **Wayland** | Window detection requires X11. `get_active_window` needs `xdotool`. |
| **Transmission** | Torrent tools need `transmission-cli` + `transmission-daemon`. |
| **Internet required** | The brain runs in the cloud (xAI API). |
| **Linux** | Tested on Ubuntu/Debian. Some features need X11. |

---

## 📄 License

[MIT](LICENSE) © 2026 hashcat916

---

<div align="center">
  <sub>Built with ❤️ and a lot of ☕</sub>
</div>
