# Lessons Learned — AILIEN Troubleshooting

_Saved 2026-06-07_

## The Skill System Bug (THE BIG ONE)
The root cause of AILIEN not being able to control the computer was in `skills/__init__.py`.
`execute_skill_tool()` returned `"Skill tool not found: {name}"` (a string) when no skill matched.
The calling code checked `if skill_result is not None:` — which was always True because it got an error
string back. This blocked ALL built-in tools from ever executing.

**Fix**: Changed `return f"Skill tool not found: {name}"` to `return None` so the code falls
through to the actual built-in tool registry.

## Don't Bypass the Program
When debugging, don't run tools directly through the terminal/bash to test things.
Run them through AILIEN itself using `-c 'command'` so the full pipeline is tested.

## Tray Icon Causes GLib Errors
The system tray icon (pystray + appindicator) causes GLib-GIO-CRITICAL D-Bus errors on Linux/XFCE.
These are harmless but clutter the terminal. Fix: only start the tray icon in --daemon mode.

## Wake Word Detector Eats CPU
In --text mode, the wake word detector was running constantly (transcribing audio every ~1 second).
This made everything feel slow. Fix: don't start the wake word detector in text/freebuff modes.

## Browser/Media Tools Need Window Targeting
Tools that use pyautogui to send keystrokes (media_play_pause, browser_navigate, etc.) send them
to the FOCUSED window. When chatting with AILIEN, the terminal is focused, so keystrokes go
to the terminal, not Firefox. Fix: use xdotool to send keys directly to the Firefox window.

## Console Verbosity
AILIEN prints a lot of INFO messages at startup (skills loaded, JARVIS features, etc.).
These are only useful for debugging. Fix: console logger at WARNING level, file logger at INFO.

## System Prompt is Critical
The AI needs clear instructions in the SYSTEM_PROMPT about:
- What tools are available
- How to check context (get_active_window)
- When to use each tool category
- Personality and tone
