"""Productivity tools — calculations, translations, weather, timers, clipboard."""
import ast
import logging
import operator
import re
import subprocess
import time
import webbrowser
from datetime import datetime
from urllib.parse import quote

import requests

from tools import tool

logger = logging.getLogger("agent")

# ---------------------------------------------------------------------------
# Safe calculator — only allows basic math operators, no function calls
# ---------------------------------------------------------------------------
_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(expr: str) -> str:
    """Evaluate a mathematical expression safely (no exec/eval)."""
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return None

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            return None
        elif isinstance(node, ast.BinOp):
            op = _ALLOWED_OPS.get(type(node.op))
            if op is None:
                return None
            left = _eval(node.left)
            right = _eval(node.right)
            if left is None or right is None:
                return None
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            op = _ALLOWED_OPS.get(type(node.op))
            if op is None:
                return None
            operand = _eval(node.operand)
            if operand is None:
                return None
            return op(operand)
        return None

    result = _eval(tree)
    if result is None:
        return None
    # Format: int if whole number, else round float
    if isinstance(result, float) and result == int(result):
        return str(int(result))
    if isinstance(result, float):
        return f"{result:.6f}".rstrip("0").rstrip(".")
    return str(result)


@tool(
    name="calculate",
    description="Perform a mathematical calculation. Supports + - * / % ** and parentheses.",
    params={
        "expression": {"type": "string", "description": "The math expression, e.g. '2 + 2', '15 * 3.5', '2 ** 10'"},
    },
    required=["expression"],
)
def calculate(expression: str) -> str:
    result = _safe_eval(expression)
    if result is None:
        return f"Could not calculate '{expression}'. Use basic math: + - * / % **"
    return f"{expression} = {result}"


# ---------------------------------------------------------------------------
# Translation (via LibreTranslate public instance or Google Translate fallback)
# ---------------------------------------------------------------------------
@tool(
    name="translate",
    description="Translate text from one language to another using LibreTranslate (free, no API key needed).",
    params={
        "text": {"type": "string", "description": "The text to translate"},
        "to": {"type": "string", "description": "Target language code: 'es' (Spanish), 'fr' (French), 'de' (German), 'it' (Italian), 'pt' (Portuguese), 'ja' (Japanese), 'zh' (Chinese), 'ko' (Korean), 'ar' (Arabic), 'ru' (Russian)", "default": "es"},
        "from_lang": {"type": "string", "description": "Source language code (default 'auto' for auto-detect)", "default": "auto"},
    },
    required=["text"],
)
def translate(text: str, to: str = "es", from_lang: str = "auto") -> str:
    try:
        resp = requests.post(
            "https://libretranslate.com/translate",
            json={"q": text, "source": from_lang, "target": to},
            timeout=10,
        )
        if resp.ok:
            result = resp.json().get("translatedText", "")
            return f"[{from_lang if from_lang != 'auto' else 'detected'} → {to}]: {result}"
        # Fallback: Google Translate URL
        from urllib.parse import quote
        lang_map = {"es": "es", "fr": "fr", "de": "de", "it": "it", "pt": "pt",
                     "ja": "ja", "zh": "zh-CN", "ko": "ko", "ar": "ar", "ru": "ru"}
        target = lang_map.get(to, to)
        url = f"https://translate.google.com/?sl={from_lang}&tl={target}&text={quote(text)}&op=translate"
        webbrowser.open(url)
        return f"Opened Google Translate for: {text[:50]}... → {to}"
    except Exception as e:
        return f"Translation failed: {e}"


# ---------------------------------------------------------------------------
# Weather (via wttr.in — free, no API key)
# ---------------------------------------------------------------------------
@tool(
    name="weather",
    description="Get the current weather for a city using wttr.in (free, no API key needed).",
    params={
        "city": {"type": "string", "description": "City name, e.g. 'London', 'New York', 'Tokyo', or 'auto' for your location", "default": "auto"},
    },
    required=[],
)
def weather(city: str = "auto") -> str:
    try:
        url = f"https://wttr.in/{quote(city)}?format=%C+%t+%h+%w+%p"
        resp = requests.get(url, timeout=10)
        if resp.ok:
            return f"Weather for {city}: {resp.text.strip()}"
        return f"Could not get weather for '{city}'."
    except Exception as e:
        return f"Weather fetch failed: {e}"


# ---------------------------------------------------------------------------
# Clipboard tools
# ---------------------------------------------------------------------------
@tool(
    name="clipboard_history",
    description="Show clipboard history (last few items copied).",
    params={},
    required=[],
)
def clipboard_history() -> str:
    """Basic clipboard viewer — shows current clipboard content."""
    try:
        import pyperclip
        text = pyperclip.paste()
        if not text:
            return "Clipboard is empty."
        preview = text[:500]
        if len(text) > 500:
            preview += "..."
        return f"Clipboard: {preview}"
    except Exception as e:
        return f"Could not read clipboard: {e}"
