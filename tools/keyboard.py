"""Keyboard control tools."""
import time

import pyautogui

from tools import tool


@tool(
    name="type_text",
    description="Type the given text as keyboard input.",
    params={
        "text": {"type": "string", "description": "The text to type"},
        "interval": {"type": "number", "description": "Delay between keystrokes in seconds (default 0.01)"},
    },
    required=["text"],
)
def type_text(text: str, interval: float = 0.01) -> str:
    pyautogui.typewrite(text, interval=interval)
    return f"Typed: {text!r}"


@tool(
    name="press_key",
    description="Press one or more keys. Use hotkey combinations like 'ctrl+c' or 'alt+tab'.",
    params={
        "keys": {"type": "string", "description": "Key or combination to press. Examples: 'enter', 'ctrl+c', 'alt+tab', 'win+d'"},
        "presses": {"type": "integer", "description": "Number of times to press (default 1)"},
        "interval": {"type": "number", "description": "Interval between presses in seconds (default 0.1)"},
    },
    required=["keys"],
)
def press_key(keys: str, presses: int = 1, interval: float = 0.1) -> str:
    # Split on '+' for combinations
    key_parts = [p.strip() for p in keys.split("+")]
    for _ in range(presses):
        if len(key_parts) == 1:
            pyautogui.press(key_parts[0])
        else:
            pyautogui.hotkey(*key_parts)
        if interval > 0:
            time.sleep(interval)
    return f"Pressed: {keys} ({presses} time(s))"


@tool(
    name="clipboard_set",
    description="Copy text to the clipboard.",
    params={
        "text": {"type": "string", "description": "Text to copy to clipboard"},
    },
    required=["text"],
)
def clipboard_set(text: str) -> str:
    import pyperclip
    pyperclip.copy(text)
    return "Text copied to clipboard."


@tool(
    name="clipboard_get",
    description="Get the current clipboard text.",
    params={},
    required=[],
)
def clipboard_get() -> str:
    import pyperclip
    try:
        text = pyperclip.paste()
        return f"Clipboard contains: {text!r}"
    except Exception as e:
        return f"Could not read clipboard: {e}"
