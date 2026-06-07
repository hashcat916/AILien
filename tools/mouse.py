"""Mouse control tools."""
import time

import pyautogui

from tools import tool

pyautogui.FAILSAFE = True  # move to corner to abort


@tool(
    name="mouse_move",
    description="Move the mouse cursor to the specified screen coordinates (x, y).",
    params={
        "x": {"type": "number", "description": "X coordinate in pixels"},
        "y": {"type": "number", "description": "Y coordinate in pixels"},
        "duration": {"type": "number", "description": "Animation duration in seconds (default 0.2)"},
    },
    required=["x", "y"],
)
def mouse_move(x: float, y: float, duration: float = 0.2) -> str:
    pyautogui.moveTo(int(x), int(y), duration=duration)
    return f"Mouse moved to ({int(x)}, {int(y)})."


@tool(
    name="mouse_click",
    description="Click the mouse at the current position or specified coordinates.",
    params={
        "x": {"type": "number", "description": "Optional X coordinate. If omitted, clicks at current position."},
        "y": {"type": "number", "description": "Optional Y coordinate"},
        "button": {"type": "string", "description": "Button: left, right, middle (default left)", "enum": ["left", "right", "middle"]},
        "clicks": {"type": "integer", "description": "Number of clicks (default 1)"},
    },
    required=[],
)
def mouse_click(x: float | None = None, y: float | None = None, button: str = "left", clicks: int = 1) -> str:
    if x is not None and y is not None:
        pyautogui.click(int(x), int(y), button=button, clicks=clicks)
        return f"Clicked {button} at ({int(x)}, {int(y)}) {clicks} time(s)."
    else:
        pyautogui.click(button=button, clicks=clicks)
        return f"Clicked {button} at current position {clicks} time(s)."


@tool(
    name="mouse_scroll",
    description="Scroll the mouse wheel up or down.",
    params={
        "amount": {"type": "integer", "description": "Positive scrolls up, negative scrolls down. Units are clicks."},
    },
    required=["amount"],
)
def mouse_scroll(amount: int) -> str:
    pyautogui.scroll(amount)
    direction = "up" if amount > 0 else "down"
    return f"Scrolled {direction} {abs(amount)} units."


@tool(
    name="mouse_drag",
    description="Drag the mouse from current position to target coordinates.",
    params={
        "x": {"type": "number", "description": "Target X coordinate"},
        "y": {"type": "number", "description": "Target Y coordinate"},
        "duration": {"type": "number", "description": "Drag duration in seconds (default 0.5)"},
        "button": {"type": "string", "description": "Button to hold during drag (default left)", "enum": ["left", "right", "middle"]},
    },
    required=["x", "y"],
)
def mouse_drag(x: float, y: float, duration: float = 0.5, button: str = "left") -> str:
    pyautogui.dragTo(int(x), int(y), duration=duration, button=button)
    return f"Dragged to ({int(x)}, {int(y)}) with {button} button."


@tool(
    name="get_mouse_position",
    description="Get the current mouse cursor position on screen.",
    params={},
    required=[],
)
def get_mouse_position() -> str:
    x, y = pyautogui.position()
    return f"Mouse is at ({x}, {y}). Screen size is {pyautogui.size()}."
