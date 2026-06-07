"""Utility tools — password generator, color picker, alarm clock, expense tracker, file organizer."""

import csv
import io
import json
import logging
import os
import random
import secrets
import shutil
import string
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pyperclip

from tools import tool

logger = logging.getLogger("agent")

# ---- Shared paths ----
_CACHE = Path(__file__).resolve().parent.parent / ".cache"
_CACHE.mkdir(exist_ok=True)
_EXPENSES_FILE = _CACHE / "expenses.json"
_ALARMS_FILE = _CACHE / "alarms.json"


# ===================================================================
# 🔑 PASSWORD GENERATOR
# ===================================================================
@tool(
    name="generate_password",
    description="Generate a strong random password and copy it to the clipboard.",
    params={
        "length": {"type": "integer", "description": "Password length (default 20, max 128)", "default": 20},
        "use_symbols": {"type": "boolean", "description": "Include special characters like !@#$%", "default": True},
        "use_numbers": {"type": "boolean", "description": "Include digits 0-9", "default": True},
        "use_uppercase": {"type": "boolean", "description": "Include uppercase letters", "default": True},
    },
    required=[],
)
def generate_password(length: int = 20, use_symbols: bool = True, use_numbers: bool = True, use_uppercase: bool = True) -> str:
    if length < 4:
        return "Password length must be at least 4."
    if length > 128:
        length = 128

    chars = string.ascii_lowercase
    if use_uppercase:
        chars += string.ascii_uppercase
    if use_numbers:
        chars += string.digits
    if use_symbols:
        chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Ensure at least one character from each selected category
    password = []
    if use_uppercase:
        password.append(secrets.choice(string.ascii_uppercase))
    if use_numbers:
        password.append(secrets.choice(string.digits))
    if use_symbols:
        password.append(secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?"))

    # Fill the rest
    while len(password) < length:
        password.append(secrets.choice(chars))

    secrets.SystemRandom().shuffle(password)
    password_str = "".join(password)

    try:
        pyperclip.copy(password_str)
        clipboard_msg = " (copied to clipboard)"
    except Exception:
        clipboard_msg = ""

    import math
    char_pool_size = len(set(chars))
    entropy = length * math.log2(char_pool_size) if char_pool_size > 0 else 0
    strength = "strong"
    if entropy < 40:
        strength = "weak"
    elif entropy < 60:
        strength = "moderate"

    return (
        f"Generated {strength} password ({length} chars){clipboard_msg}\n"
        f"  {password_str}"
    )


# ===================================================================
# 🎨 SCREEN COLOR PICKER
# ===================================================================
@tool(
    name="pick_color",
    description="Pick the color at your mouse cursor position. Returns hex and RGB values.",
    params={
        "x": {"type": "integer", "description": "X coordinate (optional — uses cursor position if omitted)", "default": None},
        "y": {"type": "integer", "description": "Y coordinate (optional — uses cursor position if omitted)", "default": None},
    },
    required=[],
)
def pick_color(x: int | None = None, y: int | None = None) -> str:
    try:
        import pyautogui
        if x is None or y is None:
            x, y = pyautogui.position()

        # Take a small screenshot around the point and read the pixel
        screenshot = pyautogui.screenshot(region=(max(0, x - 2), max(0, y - 2), 5, 5))
        # Get the center pixel
        pixel = screenshot.getpixel((2, 2))
        r, g, b = pixel[:3]
        hex_color = f"#{r:02x}{g:02x}{b:02x}"

        # Try to get a color name approximation
        color_names = {
            (0, 0, 0): "Black", (255, 255, 255): "White", (255, 0, 0): "Red",
            (0, 255, 0): "Lime", (0, 0, 255): "Blue", (255, 255, 0): "Yellow",
            (0, 255, 255): "Cyan", (255, 0, 255): "Magenta", (128, 128, 128): "Gray",
            (128, 0, 0): "Maroon", (0, 128, 0): "Green", (0, 0, 128): "Navy",
            (128, 128, 0): "Olive", (0, 128, 128): "Teal", (128, 0, 128): "Purple",
        }
        color_name = color_names.get((r, g, b), "")

        try:
            pyperclip.copy(hex_color)
            clip_msg = " — copied to clipboard"
        except Exception:
            clip_msg = ""

        parts = [f"Color at ({x}, {y}):"]
        parts.append(f"  HEX:  {hex_color}{clip_msg}")
        parts.append(f"  RGB:  rgb({r}, {g}, {b})")
        if color_name:
            parts.append(f"  Name: {color_name}")

        return "\n".join(parts)
    except ImportError:
        return "Color picker requires pyautogui (already installed)."
    except Exception as e:
        return f"Error picking color: {e}"


# ===================================================================
# ⏰ ALARM CLOCK
# ===================================================================

_alarms: dict[str, dict] = {}
_alarm_lock = threading.Lock()


def _load_alarms() -> None:
    global _alarms
    try:
        if _ALARMS_FILE.exists():
            with open(_ALARMS_FILE) as f:
                _alarms = json.load(f)
    except Exception:
        _alarms = {}


def _save_alarms() -> None:
    try:
        with open(_ALARMS_FILE, "w") as f:
            json.dump(_alarms, f, indent=2)
    except Exception as e:
        logger.warning("Failed to save alarms: %s", e)


def _alarm_worker(alarm_id: str, label: str) -> None:
    """Wait until alarm time, then play sound repeatedly."""
    while True:
        with _alarm_lock:
            alarm = _alarms.get(alarm_id)
            if alarm is None:
                return
            alarm_time = datetime.fromisoformat(alarm["time"])
            snooze_until = alarm.get("snooze_until")

        # Check snooze
        check_time = snooze_until if snooze_until else alarm_time
        if datetime.now() < check_time:
            time.sleep(5)
            continue

        # Fire!
        try:
            from utils.helpers import notify, speak
            msg = f"⏰ Alarm{f' — {label}' if label else ''}"
            speak(msg)
            notify("AILIEN Alarm", msg)

            # Play sound via ffplay
            try:
                # Try a system beep or play a sound
                subprocess.run(
                    ["paplay", "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"],
                    timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception:
                try:
                    # Fallback: terminal bell
                    print("\a", end="", flush=True)
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Alarm fire error: %s", e)

        # Repeating alarm — snooze 5 minutes
        with _alarm_lock:
            if alarm_id in _alarms:
                _alarms[alarm_id]["snooze_until"] = (datetime.now() + timedelta(minutes=5)).isoformat()
                _save_alarms()

        time.sleep(10)


@tool(
    name="set_alarm",
    description="Set an alarm that will ring at a specific time. The alarm repeats every 5 minutes until cancelled.",
    params={
        "time_str": {"type": "string", "description": 'Time in 24h format like "07:00" or "14:30", or relative like "in 10 minutes" or "in 2 hours"'},
        "label": {"type": "string", "description": "Optional label for the alarm (e.g. 'Wake up')", "default": ""},
    },
    required=["time_str"],
)
def set_alarm(time_str: str, label: str = "") -> str:
    _load_alarms()

    # Parse time
    now = datetime.now()
    alarm_dt = None

    # Relative times
    lower = time_str.lower().strip()
    if lower.startswith("in "):
        import re
        m = re.match(r"in\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?)?", lower)
        if m:
            amount = int(m.group(1))
            unit = m.group(2) or "minutes"
            if unit.startswith("second") or unit.startswith("sec"):
                alarm_dt = now + timedelta(seconds=amount)
            elif unit.startswith("hour") or unit.startswith("hr"):
                alarm_dt = now + timedelta(hours=amount)
            else:
                alarm_dt = now + timedelta(minutes=amount)

    if alarm_dt is None:
        # Try 24h time
        try:
            parts = time_str.strip().split(":")
            h, m = int(parts[0]), int(parts[1])
            alarm_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if alarm_dt <= now:
                alarm_dt += timedelta(days=1)
        except (ValueError, IndexError):
            return (
                f"Could not parse time '{time_str}'. Use 24h format like '07:00' or relative like 'in 10 minutes'."
            )

    alarm_id = f"alarm_{int(time.time())}_{random.randint(100, 999)}"
    alarm_data = {
        "time": alarm_dt.isoformat(),
        "label": label,
        "created": now.isoformat(),
    }

    with _alarm_lock:
        _alarms[alarm_id] = alarm_data
        _save_alarms()

    # Start worker
    t = threading.Thread(target=_alarm_worker, args=(alarm_id, label), daemon=True)
    t.start()

    time_str_formatted = alarm_dt.strftime("%H:%M")
    label_str = f' "{label}"' if label else ""
    return f"Alarm{label_str} set for {time_str_formatted} ({alarm_dt.strftime('%b %d')}). It will ring repeatedly until you cancel it."


@tool(
    name="cancel_alarm",
    description="Cancel a ringing alarm by its label or ID.",
    params={
        "identifier": {"type": "string", "description": "Alarm label, ID, or 'all' to cancel all alarms"},
    },
    required=["identifier"],
)
def cancel_alarm(identifier: str) -> str:
    _load_alarms()
    ident = identifier.strip().lower()

    if ident == "all":
        count = len(_alarms)
        with _alarm_lock:
            _alarms.clear()
            _save_alarms()
        return f"Cancelled all {count} alarm(s)."

    # Match by label or ID
    to_remove = []
    for aid, alarm in _alarms.items():
        if aid == ident or alarm.get("label", "").lower() == ident:
            to_remove.append(aid)

    if not to_remove:
        return f"No alarm found matching '{identifier}'."

    with _alarm_lock:
        for aid in to_remove:
            _alarms.pop(aid, None)
        _save_alarms()

    return f"Cancelled {len(to_remove)} alarm(s)."


@tool(
    name="list_alarms",
    description="List all pending alarms.",
    params={},
    required=[],
)
def list_alarms() -> str:
    _load_alarms()
    if not _alarms:
        return "No alarms set."

    lines = ["Pending alarms:"]
    for aid, alarm in sorted(_alarms.items()):
        try:
            t = datetime.fromisoformat(alarm["time"])
            label = alarm.get("label", "")
            label_str = f' "{label}"' if label else ""
            snooze = alarm.get("snooze_until")
            snooze_str = f" (snoozed until {datetime.fromisoformat(snooze).strftime('%H:%M')})" if snooze else ""
            lines.append(f"  • {t.strftime('%a %H:%M')}{label_str}{snooze_str}")
        except Exception:
            lines.append(f"  • {aid}")
    return "\n".join(lines)


# ===================================================================
# 💰 EXPENSE TRACKER
# ===================================================================

_EXPENSE_CATEGORIES = [
    "food", "transport", "housing", "utilities", "entertainment",
    "shopping", "health", "education", "bills", "other",
]


def _load_expenses() -> list[dict]:
    try:
        if _EXPENSES_FILE.exists():
            with open(_EXPENSES_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_expenses(expenses: list[dict]) -> None:
    with open(_EXPENSES_FILE, "w") as f:
        json.dump(expenses, f, indent=2)


@tool(
    name="log_expense",
    description="Log a spending entry. Track your expenses over time.",
    params={
        "amount": {"type": "number", "description": "Amount spent (e.g. 45.50)"},
        "category": {"type": "string", "description": f"Category: {', '.join(_EXPENSE_CATEGORIES)}", "default": "other"},
        "description": {"type": "string", "description": "Optional description of what was purchased", "default": ""},
    },
    required=["amount"],
)
def log_expense(amount: float, category: str = "other", description: str = "") -> str:
    category = category.lower().strip()
    if category not in _EXPENSE_CATEGORIES:
        return f"Invalid category. Choose from: {', '.join(_EXPENSE_CATEGORIES)}"

    if amount <= 0:
        return "Amount must be positive."

    expenses = _load_expenses()
    entry = {
        "amount": round(amount, 2),
        "category": category,
        "description": description,
        "date": datetime.now().isoformat(),
    }
    expenses.append(entry)
    _save_expenses(expenses)

    desc_str = f" ({description})" if description else ""
    return f"Logged: ${amount:.2f} — {category}{desc_str}"


@tool(
    name="query_expenses",
    description="Query your expense history. View spending by period and category.",
    params={
        "period": {"type": "string", "description": "'week', 'month', 'year', or 'all'", "default": "month"},
        "category": {"type": "string", "description": f"Filter by category (optional): {', '.join(_EXPENSE_CATEGORIES)}", "default": ""},
    },
    required=[],
)
def query_expenses(period: str = "month", category: str = "") -> str:
    expenses = _load_expenses()
    if not expenses:
        return "No expenses logged yet. Use log_expense to start tracking."

    now = datetime.now()
    if period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    elif period == "year":
        cutoff = now - timedelta(days=365)
    else:
        cutoff = datetime.min

    filtered = []
    for e in expenses:
        try:
            d = datetime.fromisoformat(e["date"])
            if d >= cutoff:
                if category and e["category"] != category.lower():
                    continue
                filtered.append(e)
        except Exception:
            continue

    if not filtered:
        period_label = {"week": "the last week", "month": "the last month", "year": "the last year", "all": "all time"}
        cat_str = f" in '{category}'" if category else ""
        return f"No expenses found for {period_label.get(period, period)}{cat_str}."

    total = sum(e["amount"] for e in filtered)
    by_cat: dict[str, float] = {}
    for e in filtered:
        by_cat[e["category"]] = by_cat.get(e["category"], 0) + e["amount"]

    period_label = {"week": "Week", "month": "Month", "year": "Year", "all": "All time"}
    lines = [f"{period_label.get(period, period)} spending:"]
    lines.append(f"  Total: ${total:.2f}")
    lines.append("")
    lines.append("  By category:")
    for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
        pct = (amt / total * 100) if total > 0 else 0
        lines.append(f"    {cat:15}  ${amt:>8.2f}  ({pct:.0f}%)")
    lines.append("")
    lines.append(f"  {len(filtered)} transactions")

    return "\n".join(lines)


@tool(
    name="export_expenses",
    description="Export your expense data as CSV text or save to a file.",
    params={
        "format": {"type": "string", "description": "'text' for a table, 'csv' for CSV format", "default": "text"},
        "output_file": {"type": "string", "description": "Optional file path to save to (e.g. '~/expenses.csv')", "default": ""},
    },
    required=[],
)
def export_expenses(format: str = "text", output_file: str = "") -> str:
    expenses = _load_expenses()
    if not expenses:
        return "No expenses to export."

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["date", "amount", "category", "description"])
        for e in expenses:
            try:
                d = datetime.fromisoformat(e["date"]).strftime("%Y-%m-%d %H:%M")
            except Exception:
                d = e.get("date", "")
            writer.writerow([d, e["amount"], e["category"], e.get("description", "")])
        csv_content = buf.getvalue()

        if output_file:
            try:
                out_path = Path(output_file).expanduser()
                out_path.write_text(csv_content)
                return f"Exported {len(expenses)} expenses to {out_path}"
            except Exception as e:
                return f"Could not write to '{output_file}': {e}"
        return f"CSV Export ({len(expenses)} entries):\n\n{csv_content}"

    # Text format
    total = sum(e["amount"] for e in expenses)
    lines = [f"All Expenses ({len(expenses)} entries, total: ${total:.2f}):", ""]
    for e in reversed(expenses[-30:]):  # Show last 30
        try:
            d = datetime.fromisoformat(e["date"]).strftime("%m/%d %H:%M")
        except Exception:
            d = ""
        desc = f" — {e['description']}" if e.get("description") else ""
        lines.append(f"  {d}  ${e['amount']:>7.2f}  {e['category']}{desc}")

    if output_file:
        try:
            out_path = Path(output_file).expanduser()
            out_path.write_text("\n".join(lines))
            return f"Exported expenses to {out_path}"
        except Exception as e:
            return f"Could not write to '{output_file}': {e}"

    return "\n".join(lines)


# ===================================================================
# 🗂️ FILE ORGANIZER
# ===================================================================

_FILE_CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".raw"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"],
    "Video": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"],
    "Archives": [".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", ".xz"],
    "Code": [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss", ".json", ".xml", ".yaml", ".yml", ".toml", ".sh", ".bash", ".go", ".rs", ".java", ".cpp", ".c", ".h", ".rb", ".php", ".swift", ".kt"],
    "Installers": [".deb", ".rpm", ".appimage", ".exe", ".msi", ".dmg", ".pkg"],
    "Torrents": [".torrent"],
    "Fonts": [".ttf", ".otf", ".woff", ".woff2"],
    "Other": [],
}


@tool(
    name="organize_directory",
    description="Organize files in a directory into categorized subfolders (Images, Documents, Audio, etc.).",
    params={
        "path": {"type": "string", "description": "Directory to organize (default ~/Downloads)", "default": "~/Downloads"},
        "dry_run": {"type": "boolean", "description": "If true, only show what would be moved (don't actually move)", "default": True},
    },
    required=[],
)
def organize_directory(path: str = "~/Downloads", dry_run: bool = True) -> str:
    try:
        target = Path(path).expanduser().resolve()
        if not target.is_dir():
            return f"Directory not found: {target}"

        files_to_move: list[tuple[Path, str, str]] = []  # (file, category, dest_dir)

        for f in sorted(target.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue

            ext = f.suffix.lower()
            moved = False
            for category, extensions in _FILE_CATEGORIES.items():
                if ext in extensions:
                    files_to_move.append((f, category, str(target / category)))
                    moved = True
                    break

            if not moved:
                files_to_move.append((f, "Other", str(target / "Other")))

        if not files_to_move:
            return f"No organizable files found in {target}."

        # Group by category
        by_cat: dict[str, list[Path]] = {}
        for f, cat, _ in files_to_move:
            by_cat.setdefault(cat, []).append(f)

        if dry_run:
            lines = [f"Would organize {len(files_to_move)} files in {target}:"]
            for cat, flist in sorted(by_cat.items()):
                lines.append(f"  📁 {cat}/ ({len(flist)} files)")
                for f in flist[:5]:
                    lines.append(f"    · {f.name}")
                if len(flist) > 5:
                    lines.append(f"    ... and {len(flist) - 5} more")
            lines.append("")
            lines.append("Run with dry_run=false to actually move the files.")
            return "\n".join(lines)

        # Actually move files
        moved_count = 0
        errors = []
        for f, category, dest in files_to_move:
            try:
                dest_dir = Path(dest)
                dest_dir.mkdir(exist_ok=True)
                dest_path = dest_dir / f.name
                # Handle name conflicts
                counter = 1
                while dest_path.exists():
                    stem = f.stem
                    new_name = f"{stem}_{counter}{f.suffix}"
                    dest_path = dest_dir / new_name
                    counter += 1
                shutil.move(str(f), str(dest_path))
                moved_count += 1
            except Exception as e:
                errors.append(f"    {f.name}: {e}")

        result = [f"Organized {moved_count} files in {target}:"]
        for cat, flist in sorted(by_cat.items()):
            result.append(f"  📁 {cat}/ ({len(flist)} files)")
        if errors:
            result.append("")
            result.append("Errors:")
            result.extend(errors[:5])

        return "\n".join(result)
    except Exception as e:
        return f"Error organizing directory: {e}"
