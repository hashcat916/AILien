"""Quick answers — instant responses for common queries without an LLM round-trip.

This module intercepts common questions and returns immediate answers,
making AILIEN feel snappier and more responsive (like JARVIS).
"""

import datetime
import json
import math
import random
import re
import subprocess
from typing import Any

import psutil


# ---------------------------------------------------------------------------
# Greetings & personality
# ---------------------------------------------------------------------------

_GREETINGS = [
    "At your service.",
    "Right here, boss.",
    "Listening.",
    "Ready when you are.",
    "Go ahead.",
    "I'm all ears.",
    "Yes?",
    "What can I do for you?",
    "Standing by.",
    "Present.",
]

_FAREWELLS = [
    "See you later.",
    "Call me if you need anything.",
    "I'll be here.",
    "Shutting down. It's been a pleasure.",
    "Goodbye.",
    "Until next time.",
]

_THANKS_RESPONSES = [
    "Happy to help.",
    "Anytime.",
    "That's what I'm here for.",
    "My pleasure.",
    "You got it.",
    "No problem.",
    "Glad I could assist.",
]

_STATUS_RESPONSES = [
    "All systems nominal.",
    "Everything's running smoothly.",
    "Operating within normal parameters.",
    "All good on my end.",
    "Systems are green. Ready for action.",
]

_MORNING_GREETINGS = [
    "Good morning! Ready to make today productive?",
    "Good morning. I've been waiting for you.",
    "Morning! Coffee's on me — virtually, anyway.",
    "Rise and shine. Systems are ready.",
]

_EVENING_GREETINGS = [
    "Good evening. Winding down or just getting started?",
    "Evening. Hope your day went well.",
    "Good evening. I'm here if you need me.",
]


def _time_based_greeting() -> str:
    """Return a greeting appropriate for the time of day."""
    hour = datetime.datetime.now().hour
    if 5 <= hour < 12:
        return random.choice(_MORNING_GREETINGS)
    elif 18 <= hour < 22:
        return random.choice(_EVENING_GREETINGS)
    return random.choice([
        "Good afternoon. How can I help?",
        "Afternoon. What's on your mind?",
    ])


# ---------------------------------------------------------------------------
# Quick answer registry
# ---------------------------------------------------------------------------

# (pattern, handler) — pattern is a list of keywords to match
# Handler takes the raw text and returns a response string or None to pass through

_QUICK_ANSWERS: list[tuple[list[str], callable]] = []


def _register(pattern_words: list[str]):
    """Decorator to register a quick answer handler."""
    def decorator(fn):
        _QUICK_ANSWERS.append(([w.lower() for w in pattern_words], fn))
        return fn
    return decorator


import re


def _kw_in_text(keywords: list[str], text: str) -> bool:
    """Check if any keyword appears as a whole word/phrase in text.

    Short keywords (< 4 chars) require word boundaries; longer keywords
    are checked as substrings (handles phrases like "how are you").
    """
    for kw in keywords:
        if len(kw) < 4:
            # Word boundary match for short keywords
            if re.search(rf'\b{re.escape(kw)}\b', text):
                return True
        else:
            # Substring match for longer phrases
            if kw in text:
                return True
    return False


def dispatch(text: str) -> str | None:
    """Try to handle *text* as a quick query. Returns response or None."""
    lower = text.lower().strip().rstrip(".,!?;")

    for keywords, handler in _QUICK_ANSWERS:
        if _kw_in_text(keywords, lower):
            try:
                result = handler(lower)
                if result is not None:
                    return result
            except Exception:
                pass
    return None


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@_register(["how are you", "how's it going", "what's up", "status check", "how do you feel"])
def _handle_status(lower: str) -> str | None:
    """Respond to status inquiries."""
    return random.choice(_STATUS_RESPONSES)


@_register(["thank", "thanks", "appreciate", "good job", "nice work"])
def _handle_thanks(lower: str) -> str | None:
    """Respond to thanks."""
    # Check if it's actually a thank you vs something else containing "thanks"
    if not any(w in lower for w in ["thank you", "thanks", "thanks!", "thanks."]):
        return None
    return random.choice(_THANKS_RESPONSES)


@_register(["hello", "hi", "hey", "howdy", "sup", "yo", "good morning", "good afternoon", "good evening"])
def _handle_greeting(lower: str) -> str | None:
    """Respond to greetings."""
    return _time_based_greeting()


@_register(["goodbye", "bye", "see you", "later", "cya", "catch you later"])
def _handle_farewell(lower: str) -> str | None:
    """Respond to farewells."""
    return random.choice(_FAREWELLS)


@_register(["what time", "time is it", "current time", "tell me the time", "what's the time"])
def _handle_time(lower: str) -> str | None:
    """Tell the current time."""
    now = datetime.datetime.now()
    return f"It's {now.strftime('%I:%M %p').lstrip('0')}."


@_register(["what's the date", "what day is it", "today's date", "what date", "what is today"])
def _handle_date(lower: str) -> str | None:
    """Tell the current date."""
    now = datetime.datetime.now()
    return f"Today is {now.strftime('%A, %B %d, %Y')}."


@_register(["day of the week", "what day", "what weekday"])
def _handle_day(lower: str) -> str | None:
    """Tell the current day of the week."""
    now = datetime.datetime.now()
    return f"It's {now.strftime('%A')}."


@_register(["who are you", "what are you", "tell me about yourself", "introduce yourself"])
def _handle_whoami(lower: str) -> str | None:
    """Respond to identity questions."""
    return (
        "I'm AILIEN, your AI assistant. I can control your computer, "
        "answer questions, set reminders, take screenshots, browse the web, "
        "and help you get things done faster. Think of me as your Jarvis."
    )


@_register(["what can you do", "capabilities", "help", "what do you do", "your features"])
def _handle_capabilities(lower: str) -> str | None:
    """List capabilities."""
    return (
        "I can control your mouse and keyboard, launch and close apps, "
        "take screenshots and read text from your screen, browse the web, "
        "manage files, run shell commands, check system status, "
        "set reminders and timers, and answer questions. "
        "Just tell me what you need."
    )


@_register(["are you there", "you there", "hello?", "ping", "status?"])
def _handle_ping(lower: str) -> str | None:
    """Acknowledge presence."""
    return random.choice(_GREETINGS)


@_register(["tell me a joke", "make me laugh", "say something funny", "joke"])
def _handle_joke(lower: str) -> str | None:
    """Tell a programming joke."""
    jokes = [
        "Why do programmers prefer dark mode? Because light attracts bugs.",
        "There are only 10 kinds of people in the world: those who understand binary and those who don't.",
        "Why did the developer go broke? Because he used up all his cache.",
        "A SQL query walks into a bar, walks up to two tables and asks, 'Can I join you?'",
        "Why was the JavaScript developer sad? Because he didn't Node how to Express himself.",
        "I told my computer I needed a break, and now it won't stop sending me vacation ads.",
        "Why do Python programmers wear glasses? Because they can't C.",
    ]
    return random.choice(jokes)


@_register(["motivate me", "inspire me", "give me a quote", "inspiration"])
def _handle_motivate(lower: str) -> str | None:
    """Give a motivational quote."""
    quotes = [
        "\"The only way to do great work is to love what you do.\" — Steve Jobs",
        "\"It does not matter how slowly you go as long as you do not stop.\" — Confucius",
        "\"The future belongs to those who believe in the beauty of their dreams.\" — Eleanor Roosevelt",
        "\"In the middle of difficulty lies opportunity.\" — Albert Einstein",
        "\"Success is not final, failure is not fatal: it is the courage to continue that counts.\" — Winston Churchill",
    ]
    return random.choice(quotes)


@_register(["system status", "system info", "computer status", "how's my computer", "status report"])
def _handle_system_status(lower: str) -> str | None:
    """Quick system status."""
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    # Try battery
    battery = None
    try:
        for path in __import__('pathlib').Path('/sys/class/power_supply').glob('*/capacity'):
            battery = int(path.read_text().strip())
            break
    except Exception:
        pass

    parts = [f"CPU is at {cpu}%, memory at {mem.percent}%."]
    if battery is not None:
        parts.append(f"Battery is at {battery}%.")
    return " ".join(parts)


@_register(["battery", "battery level", "battery status", "power"])
def _handle_battery(lower: str) -> str | None:
    """Check battery level."""
    try:
        for path in __import__('pathlib').Path('/sys/class/power_supply').glob('*/capacity'):
            level = int(path.read_text().strip())
            if level < 20:
                return f"Battery is at {level}%. You might want to plug in soon."
            elif level < 50:
                return f"Battery is at {level}%. Still okay, but keep an eye on it."
            return f"Battery is at {level}%. Looking good."
    except Exception:
        return None  # Fall through to LLM


@_register(["cpu", "processor", "cpu usage"])
def _handle_cpu(lower: str) -> str | None:
    """Check CPU usage."""
    cpu = psutil.cpu_percent(interval=0.5)
    if cpu > 90:
        return f"CPU is at {cpu}%. Something's working hard."
    elif cpu > 70:
        return f"CPU is at {cpu}%. Moderate load."
    return f"CPU is at {cpu}%. All quiet."


@_register(["memory", "ram", "memory usage"])
def _handle_memory(lower: str) -> str | None:
    """Check memory usage."""
    mem = psutil.virtual_memory()
    return f"Using {mem.percent}% of RAM ({mem.used // (1024**3)}GB of {mem.total // (1024**3)}GB)."


@_register(["uptime", "how long", "how long has it been on", "system uptime"])
def _handle_uptime(lower: str) -> str | None:
    """Check system uptime."""
    boot = datetime.datetime.fromtimestamp(psutil.boot_time())
    delta = datetime.datetime.now() - boot
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds // 60) % 60
    return f"System has been up for {days} day(s), {hours} hour(s), {minutes} minute(s)."


# ---------------------------------------------------------------------------
# Knowledge base commands
# ---------------------------------------------------------------------------


@_register(["list knowledge", "show knowledge", "what do you know", "knowledge base", "my notes"])
def _handle_list_knowledge(lower: str) -> str | None:
    """List available knowledge topics."""
    try:
        from brain.knowledge import list_topics
        return list_topics()
    except Exception as exc:
        return f"Knowledge base unavailable: {exc}"


@_register(["search knowledge", "find in knowledge", "search my notes", "look up"])
def _handle_search_knowledge(lower: str) -> str | None:
    """Search the knowledge base."""
    # Extract the search query
    import re as _re
    m = _re.search(r"(?:search knowledge|find in knowledge|search my notes|look up)\s+(.+)", lower)
    if not m:
        # Try simpler: "knowledge <query>"
        m = _re.search(r"knowledge\s+(.+)", lower)
    if not m:
        return "What should I search for? Try: 'search knowledge python' or 'look up linux commands'."
    query = m.group(1).strip()
    try:
        from brain.knowledge import search
        return search(query)
    except Exception as exc:
        return f"Search failed: {exc}"


@_register(["read knowledge", "open knowledge", "show me knowledge", "tell me about"])
def _handle_read_knowledge(lower: str) -> str | None:
    """Read a knowledge topic."""
    import re as _re
    m = _re.search(r"(?:read knowledge|open knowledge|show me knowledge|tell me about)\s+(.+)", lower)
    if not m:
        m = _re.search(r"knowledge\s+(.+)", lower)
    if not m:
        return "Which topic? Try: 'read knowledge linux commands'."
    topic = m.group(1).strip()
    try:
        from brain.knowledge import read
        return read(topic)
    except Exception as exc:
        return f"Read failed: {exc}"


# ---------------------------------------------------------------------------
# Reddit commands
# ---------------------------------------------------------------------------


@_register(["reddit hot", "reddit front page", "what's hot on reddit", "reddit trending", "show reddit"])
def _handle_reddit_hot(lower: str) -> str | None:
    """Get hot Reddit posts."""
    m = re.search(r"r/(\w+)", lower)
    sub = m.group(1) if m else "all"
    try:
        from brain.reddit import hot
        return hot(sub)
    except Exception as exc:
        return f"Reddit unavailable: {exc}"


@_register(["reddit top", "top posts reddit", "best of reddit", "show top reddit"])
def _handle_reddit_top(lower: str) -> str | None:
    """Get top Reddit posts."""
    m = re.search(r"r/(\w+)", lower)
    sub = m.group(1) if m else "all"
    try:
        from brain.reddit import top
        return top(sub)
    except Exception as exc:
        return f"Reddit unavailable: {exc}"


@_register(["search youtube", "youtube search", "find on youtube", "youtube videos for"])
def _handle_youtube_search(lower: str) -> str | None:
    """Search YouTube for videos."""
    m = re.search(r"(?:search youtube|youtube search|find on youtube|youtube videos for)\s+(.+)", lower)
    if m:
        query = m.group(1).strip()
        try:
            from brain.youtube import search as yt_search
            return yt_search(query)
        except Exception as exc:
            return f"YouTube search unavailable: {exc}"
    return None


# ---------------------------------------------------------------------------
# YouTube commands
# ---------------------------------------------------------------------------


@_register(["youtube trending", "youtube hot", "trending videos", "trending on youtube"])
def _handle_youtube_trending(lower: str) -> str | None:
    """Get trending YouTube videos."""
    try:
        from brain.youtube import trending
        return trending()
    except Exception as exc:
        return f"YouTube unavailable: {exc}"


# ---------------------------------------------------------------------------
# Simple math detection (handles "what's 5 + 3", "calculate 12 * 4", etc.)
# ---------------------------------------------------------------------------

_MATH_PATTERNS = [
    re.compile(r"(?:what'?s|calculate|what is|compute|solve|evaluate)\s+([\d\s+\-*/.()xX÷×]+)", re.IGNORECASE),
    re.compile(r"^([\d\s+\-*/.()xX÷×]+)$"),  # Just a math expression
]


def try_math(text: str) -> str | None:
    """Try to evaluate a math expression in the text."""
    expr = None
    for pat in _MATH_PATTERNS:
        m = pat.search(text)
        if m:
            expr = m.group(1).strip()
            break

    if expr is None:
        return None

    # Clean up the expression
    expr = expr.replace("×", "*").replace("÷", "/").replace("x", "*")

    # Safety: only allow basic math characters
    if not re.match(r'^[\d\s+\-*/().%]+$', expr):
        return None

    try:
        result = eval(expr, {"__builtins__": {}}, {})  # safe eval
        if isinstance(result, (int, float)):
            # Format nicely
            if result == int(result):
                return f"{expr.strip()} = {int(result)}"
            return f"{expr.strip()} = {result:.4f}".rstrip("0").rstrip(".")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Quick computation reference
# ---------------------------------------------------------------------------

_UNITS = {
    "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4,
    "kg": 1000, "g": 1, "lb": 0.453592, "oz": 0.0283495,
    "km": 1000, "m": 1, "cm": 0.01, "mm": 0.001, "mile": 1609.34,
    "inch": 0.0254, "foot": 0.3048, "yard": 0.9144,
}

_CONVERSION_PATTERN = re.compile(
    r"(?:convert|what'?s|how many)\s+"
    r"(\d+\.?\d*)\s*(\w+)\s+"
    r"(?:to|in|is|are|=)\s+"
    r"(\w+)",
    re.IGNORECASE,
)


def try_conversion(text: str) -> str | None:
    """Try to convert between units."""
    m = _CONVERSION_PATTERN.search(text)
    if not m:
        return None
    value = float(m.group(1))
    from_unit = m.group(2).lower()
    to_unit = m.group(3).lower()

    # Check if both units are in the same category
    if from_unit in _UNITS and to_unit in _UNITS:
        result = value * _UNITS[from_unit] / _UNITS[to_unit]
        return f"{value} {from_unit} = {result:.4f} {to_unit}".rstrip("0").rstrip(".")
    return None
