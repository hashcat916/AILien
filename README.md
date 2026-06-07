# AILIEN 👽🖥️

Control your computer with voice or text using AILIEN — an AI assistant that can control your mouse, keyboard, browser, apps, files, screen, media, torrents, brightness, servers, domains, websites, and more.

_Last updated: 2026-06-07 19:25_

## What it does

- **Voice control**: Speak commands (push-to-talk or wake-word "Hey Jarvis")
- **Text control**: Type commands in an interactive chat
- **PC automation**: 157+ tools — mouse, keyboard, screenshots, browser control, app launching, file management, shell commands, media playback, brightness control, torrent downloads, code verification, notes, email, reminders, timers, scheduled automation, system monitoring, server diagnostics, domain research, website scaffolding, tool creation, web learning
- **Self-improving**: Can create its own tools at runtime and learn from the web
- **Cloud-powered brain**: Uses xAI Grok (OpenAI-compatible API)
- **Local speech**: Whisper runs locally — your voice never leaves your machine

## Quick Start

### 1. Get an API key

**xAI (recommended)**: https://console.x.ai/ — sign up and copy your API key.

### 2. Set your API key

```bash
# Option A: Environment variable
export XAI_API_KEY="xai-..."

# Option B: .env file (auto-loaded)
echo "XAI_API_KEY=xai-..." > .env
```

### 3. Install

```bash
chmod +x setup.sh && ./setup.sh
```

### 4. Run

```bash
cd ~/Desktop/my-project
./ailien --text
```

## Modes

| Command | Mode |
|---------|------|
| `./ailien --text` | Type commands in terminal |
| `./ailien --gui` | GUI window with text + voice toggle |
| `./ailien --voice` | Push-to-talk (press Enter, speak) |
| `./ailien --wake-word` | Always listening — say "Hey Jarvis" |
| `./ailien --freebuff` | Minimal inline terminal |
| `./ailien --daemon` | Background tray icon |
| `./ailien -c "command"` | Single command and exit |
| `./ailien --serve` | HTTP API server (Open WebUI compatible) |

## All 157 Tools

### Mouse

  `mouse_move`
  `mouse_click`
  `mouse_scroll`
  `mouse_drag`
  `get_mouse_position`

### Keyboard

  `type_text`
  `press_key`
  `clipboard_set`
  `clipboard_get`

### Screen

  `take_screenshot`
  `read_screen_text`

### Apps

  `launch_app`
  `list_running_apps`
  `kill_process`
  `find_process`

### Files

  `list_directory`
  `read_file`
  `find_file`
  `open_file`

### System

  `system_info`
  `get_active_window`
  `set_volume`
  `media_play_pause`
  `media_next`
  `media_previous`
  `volume_up`
  `volume_down`
  `mute_volume`
  `unmute_volume`
  `minimize_window`
  `maximize_window`
  `restore_window`
  `focus_window`

### Browser

  `open_url`
  `browser_navigate`
  `browser_find`
  `browser_new_tab`
  `browser_close_tab`
  `browser_go_back`
  `browser_go_forward`
  `browser_refresh`
  `browser_switch_tab`
  `get_webpage_text`

### Browser Extras

  `browser_get_info`
  `browser_search`
  `browser_scroll`
  `browser_click_link`
  `browser_fill_form`

### Browser Extras


### Media

  `play_media`
  `list_media`

### Display

  `set_brightness`
  `brightness_up`
  `brightness_down`
  `get_brightness`

### Productivity

  `calculate`
  `translate`
  `weather`
  `clipboard_history`

### Reminder

  `set_reminder`
  `set_timer`
  `list_reminders`
  `cancel_reminder`

### Automation

  `add_automation`
  `list_automations`
  `remove_automation`
  `pause_automation`
  `resume_automation`
  `pause_all_automations`
  `resume_all_automations`

### Feature Toggle

  `toggle_proactive_monitoring`
  `toggle_automation`
  `get_feature_status`

### Notes

  `take_note`
  `list_notes`
  `read_note`
  `search_notes`
  `delete_note`

### Email

  `compose_email`

### Code

  `check_python_syntax`
  `run_project_tests`
  `format_python`
  `self_verify`

### Website

  `serve_directory`
  `stop_server`
  `list_servers`
  `scaffold_website`

### Server

  `ping_host`
  `dns_lookup`
  `check_port`
  `trace_route`
  `http_check`

### Domain

  `check_domain`
  `domain_whois`
  `suggest_domains`

### Gaming

  `detect_gaming_setup`
  `list_games`
  `launch_game`
  `configure_gaming`
  `check_gaming_setup`
  `install_gaming_tool`

### Reasoning

  `think`
  `create_plan`
  `list_plans`
  `complete_step`
  `self_review`
  `run_command`
  `suggest_next_steps`

### Agent Browser

  `search_capabilities`
  `install_capability`
  `list_available_capabilities`
  `find_missing_capability`

### Course

  `build_course`
  `generate_book`
  `list_courses`
  `read_lesson`
  `find_tutorials`

### Learn

  `learn_from_web`
  `learn_from_reddit`
  `learn_from_youtube`
  `recall`
  `list_learned_topics`
  `forget_topic`

### Project

  `save_preference`
  `get_preferences`
  `remove_preference`
  `project_analyze`

### Utility

  `generate_password`
  `pick_color`
  `set_alarm`
  `cancel_alarm`
  `list_alarms`
  `log_expense`
  `query_expenses`
  `export_expenses`
  `organize_directory`

### Lifestyle

  `track_package`
  `find_recipes`
  `start_weather_alerts`
  `stop_weather_alerts`
  `pdf_merge`
  `pdf_split`
  `pdf_extract_text`
  `git_status`
  `git_commit`
  `git_push`
  `git_pull`
  `git_log`

### Documentation

  `update_documentation`
  `get_documentation_status`

### Shell

  `run_shell`

### Other

  `add_torrent`
  `create_tool`
  `list_created_tools`
  `remove_created_tool`
  `torrent_pause`
  `torrent_resume`
  `torrent_status`

## Create Your Own Tools

AILIEN can create new tools at runtime using `create_tool`:
```
create_tool(name="my_tool", description="Does something",
  params='{"arg": {"type": "string"}}',
  required='["arg"]',
  code="from tools import tool\n...")
```
The tool is validated (syntax + safety), saved to `tools/generated/`, and registered immediately — no restart needed.

## Learn From the Web

AILIEN can research topics and remember them:
- `learn_from_web` — fetch a URL or search the web, extract content, save to knowledge base
- `learn_from_reddit` — save hot posts from any subreddit
- `learn_from_youtube` — search and save video results
- `recall` — search your memory for previously learned topics
- `list_learned_topics` — see everything you've learned

## Safety

- **User confirmation** required for destructive actions (delete, kill, risky shell)
- **Blocks** obviously dangerous commands (`rm -rf /`, `mkfs`, etc.)
- **Prevents path traversal** in file operations
- **Blocks** reading sensitive system files (`/etc/shadow`, `/proc`, etc.)
- **Automation engine** blocks dangerous tools from running on schedules
- **Tool creation** validates generated code — blocks dangerous imports and patterns

## Project Structure

```
.
├── main.py                   # Entry point, agent loop, system prompt
├── config.py                 # Settings (env vars, API keys, defaults)
├── ailien                    # Launcher script (activates venv)
├── setup.sh                  # One-command setup
├── requirements.txt          # Python dependencies
├── .env                      # API keys (you create this)
│
├── tools/                    # Tool functions
│   ├── __init__.py           # Tool registry + @tool decorator
│   ├── generated/            # User/AI-created tools (runtime)
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
├── brain/                    # Background engines
│   ├── reminders.py          # Reminder/timer manager (persistent)
│   ├── proactive.py          # System health monitor
│   ├── automation.py         # Scheduled task engine
│   ├── quick_answers.py      # Instant responses
│   ├── youtube.py, reddit.py # Content fetchers
│   ├── notifications.py      # Desktop notification mirror
│   ├── knowledge.py          # Note/knowledge base
│   ├── toolmaker.py          # Self-tool-creation engine
│   └── learner.py            # Web learning engine
│
├── audio/                    # Recording, transcription, wake word
├── gui/                      # VoiceWindow, overlay, tray icon
├── llm/                      # API client
├── safety/                   # Safety guard & confirmations
├── skills/                   # User-defined skill plugins
├── conversations/            # Saved chat history
├── wake_words/               # Custom wake word models
└── .cache/                   # Logs, automations, reminders, learner
```

## Configuration

Set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `XAI_API_KEY` | *(required)* | xAI API key |
| `CLOUD_MODEL` | `grok-4.3` | LLM model for reasoning + tool calling |
| `CLOUD_BASE_URL` | `https://api.x.ai/v1` | API endpoint |
| `VISION_MODEL` | `grok-4.3` | Vision model for screenshot analysis |
| `WHISPER_MODEL` | `tiny` | Whisper size |
| `TTS_ENGINE` | `pyttsx3` | `pyttsx3` (offline) or `edge` (natural) |
| `JARVIS_REMINDERS` | `true` | Enable reminder/timer system |
| `JARVIS_PROACTIVE` | `true` | Enable battery/CPU monitoring |
| `JARVIS_QUICK_ANSWERS` | `true` | Enable instant responses |
| `CONVERSATION_AUTO_SAVE` | `true` | Auto-save chat history |
| `SKILLS_ENABLED` | `true` | Enable skill plugins |
| `AGENT_VOICE_FEEDBACK` | `true` | Text-to-speech on/off |
| `WAKE_WORD_CHUNK_MAX_DURATION` | `1.0` | Max seconds per audio chunk |
| `LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING |

## Environment Variables Quick Reference

```bash
# Required: at least one API key
export XAI_API_KEY="xai-..."

# Optional overrides
export CLOUD_MODEL="grok-4.3"
export WHISPER_MODEL="tiny"
export TTS_ENGINE="pyttsx3"
export JARVIS_PROACTIVE="true"
export JARVIS_REMINDERS="true"
export AGENT_VOICE_FEEDBACK="true"
export CONVERSATION_AUTO_SAVE="true"
```

## Custom Wake Words

Add to `.env` to customize wake phrases:
```env
AGENT_WAKE_WORDS=hey alan, what's up alan, hello alan
```

For Picovoice Porcupine (offline), see `wake_words/README.md`.

## Known Limitations

- **Wayland**: Window detection requires X11. `get_active_window` needs `xdotool`.
- **Transmission**: Torrent tools need `transmission-cli` + `transmission-daemon`.
- **Internet required**: The brain runs in the cloud.
- **Linux**: Tested on Ubuntu/Debian. Some features need X11.

## License

MIT
