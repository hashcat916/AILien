# AILIEN 👽🖥️

Control your computer with voice or text using AILIEN.

## What it does

- **Voice control**: Speak commands and the agent listens, transcribes locally with Whisper, then executes actions via a cloud LLM API.
- **Text control**: Type commands in an interactive chat interface.
- **PC automation**: Mouse, keyboard, screenshots, app launching, file management, shell commands, and more.
- **Cloud-powered brain**: Uses an OpenAI-compatible API (xAI, Groq, OpenAI, etc.) for reasoning and tool calling.
- **Local speech**: Whisper runs locally for privacy — your voice never leaves your machine.

> **Local version preserved**: The original fully-local Ollama-based agent is backed up in `local_agent_backup/` for offline use.

## Requirements

- Python 3.10+
- Linux (tested on Ubuntu/Debian). Some features work on macOS/Windows with minor tweaks.
- A microphone (for voice mode)
- An **API key** (free tier available at https://console.groq.com/keys for Groq, or https://console.x.ai/ for xAI)
- Optional: [Ollama](https://ollama.com/) for offline fallback or local vision

## Quick Start

### 1. Get a Groq API key

Sign up free at https://console.groq.com/keys and copy your API key.

### 2. Set your API key

```bash
export GROQ_API_KEY="gsk_..."
```

Or create a `.env` file in the project root:
```
GROQ_API_KEY=gsk_...
```

### 3. Install (one command)

```bash
chmod +x setup.sh && ./setup.sh
```

This creates a virtual environment, installs all dependencies, generates icons, and creates desktop shortcuts.

Or manually:
```bash
pip install -r requirements.txt
```

> **Hardware note**: Speech recognition (Whisper) still runs locally. On constrained hardware:
> - Use `tiny` Whisper model (default) for faster transcription
> - `easyocr` requires PyTorch which is heavy — if you don't need OCR, remove `easyocr` from `requirements.txt`

### 4. Run the agent

**Text mode** (default):
```bash
python main.py
```

**Voice mode**:
```bash
python main.py --voice
```

**Wake-word mode** (continuously listens for "Hey AILIEN"):
```bash
python main.py --wake-word
```

**Single command**:
```bash
python main.py -c "Open https://github.com"
```

**API server** (for Open WebUI):
```bash
python main.py --serve
```

**With conversation memory**:
```bash
python main.py --conversation my_chat.json    # Load previous conversation
python main.py --list-conversations             # List saved chats
python main.py -c "hello" --save-conversation result.json
```

## Available Commands

While in text mode, type:
- `quit` / `exit` / `q` — stop the agent
- `clear` — reset conversation history

## Tools the Agent Can Use

| Category | Tools |
|----------|-------|
| **Mouse** | `mouse_move`, `mouse_click`, `mouse_scroll`, `mouse_drag`, `get_mouse_position` |
| **Keyboard** | `type_text`, `press_key`, `clipboard_get`, `clipboard_set` |
| **Screen** | `take_screenshot`, `read_screen_text` (OCR) |
| **Apps** | `launch_app`, `list_running_apps`, `kill_process`, `find_process` |
| **Files** | `list_directory`, `read_file`, `find_file`, `open_file` |
| **Shell** | `run_shell` |
| **System** | `system_info`, `get_active_window`, `set_volume` |
| **Browser** | `open_url`, `browser_navigate`, `browser_find`, `browser_new_tab`, `browser_close_tab`, `browser_go_back`, `browser_go_forward`, `browser_refresh`, `browser_switch_tab`, `get_webpage_text` |

## Safety

The agent includes a safety guard that:
- Requires **user confirmation** for destructive actions (deleting files, killing processes, risky shell commands, `sudo`, etc.)
- Blocks obviously dangerous commands (`rm -rf /`, `mkfs`, etc.)
- Prevents path traversal in file operations
- Blocks reading sensitive system files (`/etc/shadow`, `/proc`, etc.)

## System Tray Icon

A cute alien system tray icon appears when the agent starts. Right-click it for a context menu with:

- **Live status** — shows what the agent is doing (Idle, Listening, Thinking, Speaking)
- **Voice feedback** toggle — turn TTS on/off
- **Confirm dangerous actions** toggle — disable confirmation prompts (not recommended)
- **Show / Hide overlay** — toggle the floating status window
- **Open log file** — opens the agent log in your default text editor
- **Quit** — gracefully shuts down the agent

The alien icon also changes color to match the agent's state:
- 🟢 Green — listening
- 🟡 Yellow — thinking
- 🔵 Blue — speaking
- ⬜ Gray — idle

> **Note**: The tray icon uses `pystray`. On some Linux desktops you may need to whitelist the app in your panel's tray settings for the icon to appear.

## Desktop Notifications 👽

The agent shows a desktop toast when it starts (`"Agent is running 👽"`) and when it stops (`"Agent stopped"`). These use your system's native notification daemon via D-Bus for best integration.

## Configuration

Set environment variables or edit `config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUD_API_KEY` | *(required)* | Your API key (xAI, Groq, OpenAI, etc.) |
| `CLOUD_MODEL` | `grok-4.3` | Cloud model for reasoning + tool calling |
| `CLOUD_BASE_URL` | `https://api.x.ai/v1` | API endpoint URL |
| `VISION_MODEL` | `grok-2-vision-1212` | Vision model for screenshot analysis |
| `WHISPER_MODEL` | `tiny` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`) |
| `WHISPER_VAD_FILTER` | `false` | Enable Silero VAD filtering (disabled by default — was too aggressive) |
| `AGENT_VOICE_FEEDBACK` | `true` | Enable text-to-speech responses |
| `AGENT_CONFIRM_DANGEROUS` | `true` | Require confirmation for risky actions |
| `WAKE_WORD_CHUNK_MAX_DURATION` | `4.0` | Max seconds per wake-word listen chunk |
| `WAKE_WORD_CHUNK_SILENCE_DURATION` | `0.8` | Seconds of silence to end a chunk |
| `OLLAMA_MODEL` | `llama3.2:1b` | Fallback local model (optional) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama fallback URL |
| `CONVERSATION_AUTO_SAVE` | `true` | Auto-save conversation history after each response |
| `CONVERSATION_MAX_HISTORY` | `24` | Max messages kept in context window |
| `SKILLS_ENABLED` | `true` | Enable the skill/plugin system |
| `TTS_ENGINE` | `edge` | TTS engine: `edge` (natural, internet) or `pyttsx3` (offline, robotic) |

## Project Structure

```
.
├── main.py                 # Entry point and agent loop
├── config.py               # Settings and constants
├── requirements.txt        # Python dependencies
├── audio/
│   ├── recorder.py         # Microphone recording with silence detection
│   └── transcriber.py      # Local Whisper speech-to-text
├── gui/
│   ├── overlay.py          # Floating status overlay window
│   └── tray.py             # System tray icon with alien and settings menu
├── llm/
│   └── cloud_client.py     # Cloud LLM client (xAI/Groq) with tool calling
├── tools/
│   ├── mouse.py            # Mouse control
│   ├── keyboard.py         # Keyboard control
│   ├── screen.py           # Screenshots and OCR
│   ├── apps.py             # Application management
│   ├── browser.py           # Browser automation (open URLs, tab control, page text)
│   ├── files.py            # File operations
│   ├── shell.py            # Shell command execution
│   └── system.py           # System info and control
├── safety/
│   └── guard.py            # Safety checks and confirmations
└── utils/
    └── helpers.py          # Logging, TTS, desktop notifications
```

## New Features

### 🧠 Conversation Memory
AILIEN can now save and load conversations. Chat history persists across restarts:

```bash
# Auto-saves after every response (enabled by default)
python main.py

# List saved conversations
python main.py --list-conversations

# Load a previous conversation to continue where you left off
python main.py --conversation conversation_20250101_120000.json

# Save a single-command response
python main.py -c "check my disk space" --save-conversation disk_check.json
```

### 🧩 Skill/Plugin System
Extend AILIEN with custom skills! Drop a Python file into `skills/` and it's automatically loaded:

```python
# skills/weather.py
from skills import Skill, tool

class WeatherSkill(Skill):
    name = "weather"
    description = "Gets the weather"

    @tool(description="Get weather for a city")
    def get_weather(self, city: str) -> str:
        return f"The weather in {city} is sunny, 72°F."
```

Skills are discovered automatically — no configuration needed. See `skills/example_skill.py` for a template.

### 🌊 Streaming API
The API server now supports streaming (SSE) responses. Open WebUI and other tools get real-time word-by-word responses:

```bash
python main.py --serve
# Then use with any OpenAI-compatible client with stream=true
```

### 🚀 One-Command Setup
```bash
chmod +x setup.sh && ./setup.sh
```
This creates the virtual environment, installs dependencies, generates icons, and creates desktop shortcuts.

## Vision Support

The agent sends screenshots to a **cloud vision model** (via Groq) which returns a detailed text description of the UI. This lets the agent "see" the screen before interacting with it.

The default vision model is `llama-3.2-11b-vision-preview` on Groq. If vision is unavailable, the agent gracefully degrades to OCR (`read_screen_text`) or a plain screenshot note.

> **Local fallback**: If you prefer fully-local vision, the `local_agent_backup/` directory contains the original Ollama-based vision setup.

## Known Limitations

- **Wayland**: Window detection (`get_active_window`) requires X11. It won't work on Wayland without `xdotool` compatibility.
- **OCR**: `easyocr` is heavy and slow to initialize on first use.
- **Internet required**: The brain runs in the cloud — you need an internet connection. The local backup in `local_agent_backup/` works offline with Ollama.
- **Groq vision**: Not all Groq models support vision; `llama-3.2-11b-vision-preview` is the current option.

## License

MIT
