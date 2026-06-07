"""Display brightness control tools."""

import subprocess
from pathlib import Path

from tools import tool

# ---------------------------------------------------------------------------
# Backlight detection (sysfs)
# ---------------------------------------------------------------------------
_BACKLIGHT_DIR = Path("/sys/class/backlight")
_BACKLIGHT_PATH: Path | None = None


def _detect_backlight() -> Path | None:
    """Find the primary backlight device via sysfs."""
    global _BACKLIGHT_PATH
    if _BACKLIGHT_PATH is not None:
        return _BACKLIGHT_PATH
    try:
        devices = sorted(_BACKLIGHT_DIR.iterdir())
        if devices:
            _BACKLIGHT_PATH = devices[0]
            return _BACKLIGHT_PATH
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return None


def _get_sysfs_brightness() -> tuple[int, int] | None:
    """Return (current, max) brightness from sysfs, or None."""
    backlight = _detect_backlight()
    if backlight is None:
        return None
    try:
        max_val = int((backlight / "max_brightness").read_text().strip())
        cur_val = int((backlight / "brightness").read_text().strip())
        return (cur_val, max_val)
    except (FileNotFoundError, PermissionError, ValueError, OSError):
        return None


def _set_sysfs_brightness(value: int) -> bool:
    """Set brightness via sysfs. Requires appropriate permissions."""
    backlight = _detect_backlight()
    if backlight is None:
        return False
    try:
        (backlight / "brightness").write_text(str(value))
        return True
    except (PermissionError, OSError):
        return False


def _get_xrandr_brightness() -> tuple[float, str] | None:
    """Return (current_brightness, output_name) via xrandr, or None."""
    try:
        result = subprocess.run(
            ["xrandr", "--verbose"],
            capture_output=True, text=True, timeout=5,
        )
        output = None
        brightness = 1.0
        for line in result.stdout.splitlines():
            # Track which output we're on
            if " connected " in line:
                output = line.split()[0]
            if output and "Brightness:" in line:
                try:
                    brightness = float(line.split()[-1])
                except (ValueError, IndexError):
                    pass
                return (brightness, output)
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _set_xrandr_brightness(level: float) -> bool:
    """Set brightness via xrandr (0.0 – 1.0). Works on all X11 systems."""
    try:
        # Find the connected output
        result = subprocess.run(
            ["xrandr", "--verbose"],
            capture_output=True, text=True, timeout=5,
        )
        output = None
        for line in result.stdout.splitlines():
            if " connected " in line:
                output = line.split()[0]
                break
        if not output:
            return False

        subprocess.run(
            ["xrandr", "--output", output, "--brightness", f"{level:.2f}"],
            check=True, capture_output=True, timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


# ---------------------------------------------------------------------------
# Percent helpers
# ---------------------------------------------------------------------------

def _to_percent(sysfs: tuple[int, int]) -> int:
    """Convert sysfs (current, max) to a 0–100 percentage."""
    cur, mx = sysfs
    if mx == 0:
        return 50
    return round(cur / mx * 100)


def _from_percent(pct: int, mx: int) -> int:
    """Convert a 0–100 percentage to a sysfs value given *mx*."""
    pct = max(0, min(100, pct))
    return round(pct / 100 * mx)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool(
    name="set_brightness",
    description="Set the screen brightness to a specific percentage (0–100).",
    params={
        "level": {
            "type": "integer",
            "description": "Brightness level from 0 to 100 percent",
        },
    },
    required=["level"],
)
def set_brightness(level: int) -> str:
    """Set brightness to *level*% using sysfs if available, otherwise xrandr."""
    level = max(0, min(100, level))

    # Try sysfs first (hardware backlight, more precise)
    sysfs = _get_sysfs_brightness()
    if sysfs is not None:
        _, mx = sysfs
        value = _from_percent(level, mx)
        if _set_sysfs_brightness(value):
            return f"Brightness set to {level}%."

    # Fallback: xrandr
    cur_xrandr = _get_xrandr_brightness()
    if cur_xrandr is not None:
        xr_level = level / 100.0
        if _set_xrandr_brightness(xr_level):
            return f"Brightness set to {level}% (via xrandr)."

    return "Could not set brightness. No backlight device found and xrandr unavailable."


@tool(
    name="brightness_up",
    description="Increase screen brightness by a percentage step.",
    params={
        "step": {
            "type": "integer",
            "description": "Amount to increase brightness by (default 10)",
            "default": 10,
        },
    },
    required=[],
)
def brightness_up(step: int = 10) -> str:
    """Increase brightness by *step*%."""
    step = max(1, min(100, step))

    # Try sysfs first
    sysfs = _get_sysfs_brightness()
    if sysfs is not None:
        cur_pct = _to_percent(sysfs)
        new_pct = min(100, cur_pct + step)
        _, mx = sysfs
        if _set_sysfs_brightness(_from_percent(new_pct, mx)):
            return f"Brightness increased to {new_pct}%."

    # Fallback xrandr
    cur_xrandr = _get_xrandr_brightness()
    if cur_xrandr is not None:
        cur_pct = round(cur_xrandr[0] * 100)
        new_pct = min(100, cur_pct + step)
        if _set_xrandr_brightness(new_pct / 100.0):
            return f"Brightness increased to {new_pct}% (via xrandr)."

    return "Could not increase brightness."


@tool(
    name="brightness_down",
    description="Decrease screen brightness by a percentage step.",
    params={
        "step": {
            "type": "integer",
            "description": "Amount to decrease brightness by (default 10)",
            "default": 10,
        },
    },
    required=[],
)
def brightness_down(step: int = 10) -> str:
    """Decrease brightness by *step*%."""
    step = max(1, min(100, step))

    sysfs = _get_sysfs_brightness()
    if sysfs is not None:
        cur_pct = _to_percent(sysfs)
        new_pct = max(0, cur_pct - step)
        _, mx = sysfs
        if _set_sysfs_brightness(_from_percent(new_pct, mx)):
            return f"Brightness decreased to {new_pct}%."

    cur_xrandr = _get_xrandr_brightness()
    if cur_xrandr is not None:
        cur_pct = round(cur_xrandr[0] * 100)
        new_pct = max(0, cur_pct - step)
        if _set_xrandr_brightness(new_pct / 100.0):
            return f"Brightness decreased to {new_pct}% (via xrandr)."

    return "Could not decrease brightness."


@tool(
    name="get_brightness",
    description="Show the current screen brightness level.",
    params={},
    required=[],
)
def get_brightness() -> str:
    """Report current brightness percentage."""
    sysfs = _get_sysfs_brightness()
    if sysfs is not None:
        pct = _to_percent(sysfs)
        return f"Screen brightness is at {pct}%."

    xrandr = _get_xrandr_brightness()
    if xrandr is not None:
        pct = round(xrandr[0] * 100)
        return f"Screen brightness is at {pct}% (via xrandr)."

    return "Could not determine brightness."
