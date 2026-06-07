"""System information and control tools."""
import shutil
from datetime import datetime

import psutil

from tools import tool


@tool(
    name="system_info",
    description="Get system information including CPU, memory, disk, and uptime.",
    params={},
    required=[],
)
def system_info() -> str:
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    cpu_percent = psutil.cpu_percent(interval=1)
    info = (
        f"CPU: {cpu_percent}% used, {psutil.cpu_count()} cores\n"
        f"Memory: {mem.percent}% used ({mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB)\n"
        f"Disk: {disk.used // (1024**3)}GB used / {disk.total // (1024**3)}GB total\n"
        f"Boot time: {boot_time}\n"
        f"Platform: {__import__('platform').platform()}"
    )
    return info


@tool(
    name="get_active_window",
    description="Get information about the currently focused window.",
    params={},
    required=[],
)
def get_active_window() -> str:
    try:
        import Xlib.display
        display = Xlib.display.Display()
        root = display.screen().root
        window_id = root.get_full_property(
            display.intern_atom("_NET_ACTIVE_WINDOW"),
            Xlib.X.AnyPropertyType
        ).value[0]
        window = display.create_resource_object("window", window_id)
        name = window.get_wm_name()
        class_ = window.get_wm_class()
        display.close()
        return f"Active window: {name} (class: {class_})"
    except Exception:
        try:
            # Fallback using xdotool
            import subprocess
            result = subprocess.run(["xdotool", "getactivewindow", "getwindowname"], capture_output=True, text=True)
            return f"Active window: {result.stdout.strip()}"
        except Exception as e:
            return f"Could not get active window: {e}"


@tool(
    name="set_volume",
    description="Set the system master volume level.",
    params={
        "level": {"type": "integer", "description": "Volume level 0-100"},
    },
    required=["level"],
)
def set_volume(level: int) -> str:
    level = max(0, min(100, level))
    try:
        import subprocess
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"], check=True)
        return f"Volume set to {level}%."
    except Exception as e:
        return f"Failed to set volume: {e}"


def _send_key_to_window(window_class: str, key: str) -> bool:
    """Send a keyboard key to a specific window by class using xdotool.

    This avoids the problem of keystrokes going to the wrong (focused)
    window — the key is delivered directly to the target window.
    """
    import subprocess
    try:
        # Find the window ID
        result = subprocess.run(
            ["xdotool", "search", "--class", window_class],
            capture_output=True, text=True, timeout=5,
        )
        wid = result.stdout.strip().split("\n")[0] if result.stdout.strip() else None
        if not wid:
            return False
        # Send the key directly to that window (doesn't steal focus)
        subprocess.run(
            ["xdotool", "key", "--window", wid, key],
            capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


@tool(
    name="media_play_pause",
    description="Toggle play/pause for media playing in Firefox (YouTube, etc.).",
    params={},
    required=[],
)
def media_play_pause() -> str:
    if _send_key_to_window("firefox", "XF86AudioPlay"):
        return "Toggled play/pause."
    # Fallback: try pyautogui
    try:
        import pyautogui
        pyautogui.press("playpause")
        return "Toggled play/pause."
    except Exception as e:
        return f"Failed to toggle play/pause: {e}"


@tool(
    name="media_next",
    description="Skip to the next track in Firefox.",
    params={},
    required=[],
)
def media_next() -> str:
    if _send_key_to_window("firefox", "XF86AudioNext"):
        return "Skipped to next track."
    try:
        import pyautogui
        pyautogui.press("nexttrack")
        return "Skipped to next track."
    except Exception as e:
        return f"Failed to skip track: {e}"


@tool(
    name="media_previous",
    description="Go back to the previous track in Firefox.",
    params={},
    required=[],
)
def media_previous() -> str:
    if _send_key_to_window("firefox", "XF86AudioPrev"):
        return "Went back to previous track."
    try:
        import pyautogui
        pyautogui.press("prevtrack")
        return "Went back to previous track."
    except Exception as e:
        return f"Failed to go back: {e}"


@tool(
    name="volume_up",
    description="Increase the system volume by 5%.",
    params={},
    required=[],
)
def volume_up() -> str:
    try:
        import subprocess
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"], check=True)
        return "Volume increased."
    except Exception as e:
        return f"Failed to increase volume: {e}"


@tool(
    name="volume_down",
    description="Decrease the system volume by 5%.",
    params={},
    required=[],
)
def volume_down() -> str:
    try:
        import subprocess
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"], check=True)
        return "Volume decreased."
    except Exception as e:
        return f"Failed to decrease volume: {e}"


@tool(
    name="mute_volume",
    description="Mute the system audio.",
    params={},
    required=[],
)
def mute_volume() -> str:
    try:
        import subprocess
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"], check=True)
        return "Audio muted."
    except Exception as e:
        return f"Failed to mute: {e}"


@tool(
    name="unmute_volume",
    description="Unmute the system audio.",
    params={},
    required=[],
)
def unmute_volume() -> str:
    try:
        import subprocess
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], check=True)
        return "Audio unmuted."
    except Exception as e:
        return f"Failed to unmute: {e}"


# ---------------------------------------------------------------------------
# Window management
# ---------------------------------------------------------------------------

@tool(
    name="minimize_window",
    description="Minimize the currently focused window.",
    params={},
    required=[],
)
def minimize_window() -> str:
    try:
        import subprocess
        subprocess.run(
            ["xdotool", "getactivewindow", "windowminimize"],
            check=True,
            capture_output=True,
        )
        return "Window minimized."
    except Exception as e:
        return f"Failed to minimize window: {e}"


@tool(
    name="maximize_window",
    description="Maximize the currently focused window.",
    params={},
    required=[],
)
def maximize_window() -> str:
    try:
        import subprocess
        subprocess.run(
            ["xdotool", "getactivewindow", "windowmaximize"],
            check=True,
            capture_output=True,
        )
        return "Window maximized."
    except Exception as e:
        return f"Failed to maximize window: {e}"


@tool(
    name="restore_window",
    description="Restore (un-maximize) the currently focused window to its normal size.",
    params={},
    required=[],
)
def restore_window() -> str:
    try:
        import subprocess
        subprocess.run(
            ["xdotool", "getactivewindow", "windowrestore"],
            check=True,
            capture_output=True,
        )
        return "Window restored."
    except Exception as e:
        return f"Failed to restore window: {e}"


@tool(
    name="focus_window",
    description="Raise and focus a window by its class name or title.",
    params={
        "class_name": {"type": "string", "description": "Window class name to search for (e.g. 'firefox', 'google-chrome', 'code')"},
        "title": {"type": "string", "description": "Window title substring to search for (fallback if class not found)"},
    },
    required=[],
)
def focus_window(class_name: str = "", title: str = "") -> str:
    try:
        import subprocess
        if class_name:
            result = subprocess.run(
                ["xdotool", "search", "--class", class_name, "windowactivate"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return f"Focused window with class '{class_name}'."
        if title:
            result = subprocess.run(
                ["xdotool", "search", "--name", title, "windowactivate"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return f"Focused window with title '{title}'."
        return "Window not found."
    except Exception as e:
        return f"Failed to focus window: {e}"
