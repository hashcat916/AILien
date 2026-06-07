# 👽 AILIEN — Quick Start Guide

Your project is at: **`/home/alan/Desktop/my-project`**

---

## ✅ The SIMPLEST way to run it

```bash
cd ~/Desktop/my-project
./ailien --text
```

That's it. A chat window opens where you can type commands.

### What you'll see

```
        .===============================.
        |                               |
        |      👽   A  I  L  I  E  N   |
        |                               |
        `===============================`

AILIEN - Text Mode
Type your command or 'quit' to exit.
Type /freebuff for minimal inline style.
Type /mute or /voice to toggle TTS feedback.
Want voice? Use: ./ailien --wake-word

You:
```

### Things to try

| You type | What happens |
|----------|-------------|
| `"Hello"` | AI responds |
| `"Open https://google.com"` | Opens in Firefox |
| `"What's my system status?"` | CPU, memory, battery |
| `"Take a screenshot"` | Captures + AI describes it |
| `"Open firefox"` | Launches Firefox |
| `"Pause video"` | Pauses YouTube in Firefox |
| `"Set a timer for 30 seconds"` | Countdown timer |
| `"Remind me in 5 minutes to check email"` | Persistent reminder |
| `"What's the weather in London?"` | Free weather (no API key) |
| `"Play feel good inc"` | Searches & plays local media |
| `"Brightness down"` | Dims the screen |
| `"Open youtube and play lofi hip hop"` | Multi-step browser task |
| `"List my notes"` | Shows saved knowledge notes |
| `"Check Python syntax"` | Validates project files |
| `quit` | Exit |

---

## 🪟 GUI Window

```bash
./ailien --gui
```

Floating window with text input + voice toggle + button to stop mid-response.

---

## 🎤 Voice mode (push-to-talk)

```bash
./ailien --voice
```

Press Enter, speak, silence stops recording, AI responds.

---

## 👂 Wake word mode (always listening)

```bash
./ailien --wake-word
```

Say **"hey jarvis"** or **"hey ailien"** followed by your command.

Voice shortcuts while listening:
- `"screenshot"` — capture screen
- `"status"` — system info
- `"volume up/down"` — adjust
- `"play/pause/next"` — media
- `"go to sleep"` — pause listening
- `"wake up"` — resume
- `"open firefox"` — launch app
- `"minimize window"` — window management

---

## 🤖 Automation & Background Features

**Reminders & Timers** (persist across restarts):
```
"remind me in 10 minutes to check the oven"
"set a timer for 3 minutes"
"list my reminders"
"cancel the oven reminder"
```

**Scheduled Automation** (runs tools on a schedule):
```
"check the weather every hour"
"tell me system status every 30 minutes"
"list my automations"
"pause the weather check"
```

**Feature Toggles** (turn background stuff on/off):
```
"turn off proactive monitoring"
"stop all automations"
"what features are running?"
```

---

## 📋 All modes at a glance

| Command | What it does |
|---------|-------------|
| `./ailien --text` | Type commands in terminal |
| `./ailien --gui` | GUI window with text + voice |
| `./ailien --voice` | Push-to-talk voice mode |
| `./ailien --wake-word` | Say "hey jarvis" to activate |
| `./ailien --freebuff` | Minimal terminal mode |
| `./ailien --daemon` | Runs in background (tray icon) |
| `./ailien -c "do something"` | Run one command and exit |
| `./ailien --serve` | HTTP API server |
| `./ailien --help` | See all options |

---

## 🛑 Common problems

### "command not found: ./ailien"
You need to be in the project directory first:
```bash
cd ~/Desktop/my-project
```

### API key not set
Create a `.env` file in the project folder:
```bash
echo "XAI_API_KEY=xai-..." > .env
```

### "transmission-remote not found"
Torrent tools need `transmission-cli`:
```bash
sudo apt-get install transmission-cli transmission-daemon
```

### All dependencies are already installed
Everything is in the `.venv` folder — you're good.
