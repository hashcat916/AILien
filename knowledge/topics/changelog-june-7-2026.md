# AILIEN Changelog — June 7, 2026

## Tray Icon & Notifications
- **Downloaded real alien PNG icon** from Flaticon (64×64) — replaces the old PIL-drawn emoji rendering
- Tray icon now composites the downloaded alien PNG onto status-colored circular backgrounds (gray/green/yellow/blue)
- Notification system rewritten to use `notify-send` with the downloaded icon instead of tiny plyer notifications
- No more white overlay popup window in daemon mode (`no_overlay=True`)
- Filled notification icon: `.cache/ailien_icon.png`

## Duplicate Instance Prevention
- **PID file lock** at `.cache/ailien_daemon.pid` prevents launching multiple daemon instances
- If already running, second launch shows a notification and exits
- PID file automatically cleaned up on graceful exit (Quit via tray menu)
- Added `import os` at top of `main.py`

## Wake Word Improvements
- Added **"hey alien"**, **"ok alien"**, **"alien"** to wake words (matches natural pronunciation — users say "alien" not "ailien")
- **Whisper model pre-loads** at daemon startup (~6s) so first utterance doesn't trigger a 4-second model download delay
- `faster-whisper` v1.2.1 installed and cached at `~/.cache/huggingface/hub/models--Systran--faster-whisper-tiny/`
- D-Bus dependencies installed: `dbus-python` 1.4.0 + system `python3-gi` symlinked into venv

## Desktop Shortcuts (cleaned up)
- **2 shortcuts only** (was 4):
  - `AILIEN.desktop` — GUI/daemon mode (`--daemon`, `Terminal=false`)
  - `AILIEN-Terminal.desktop` — Terminal text chat (`--text`, `Terminal=true`)
- Old shortcuts deleted: `AILIEN-Server`, `AILIEN-Text`, `AILIEN-Voice`
- Old PNG icon files deleted (`icon.png`, `icon-server.png`, `icon-text.png`, `icon-voice.png`)

## Files Modified
- `gui/tray.py` — Rewritten icon drawing: loads downloaded PNG, composites on status-colored circles
- `utils/helpers.py` — `notify()` uses `notify-send` with icon; icon path helper simplified
- `config.py` — Added "hey alien", "ok alien", "alien" to `AGENT_WAKE_WORDS`
- `main.py` — PID file lock, whisper pre-load, merged startup notification, banner suppressed in daemon, `import os` added

## System Dependencies Installed
- `libdbus-1-dev`, `libglib2.0-dev`, `libgirepository1.0-dev` (system packages)
- `dbus-python` 1.4.0 (via pip into venv)
- Symlinked system `gi` module into venv for notification support
