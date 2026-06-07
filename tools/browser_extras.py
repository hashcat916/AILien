"""Browser automation tools — click, search, scroll, fill forms, get info."""
import re
import time
import webbrowser
from urllib.parse import quote, urlparse

import pyautogui
import requests

from tools import tool
from tools.browser import _browser_key, _browser_type, _browser_wid, _focus_browser


@tool(
    name="browser_get_info",
    description="Get the current page title and URL from the active browser tab.",
    params={},
    required=[],
)
def browser_get_info() -> str:
    """Get the active browser tab's title and URL using Ctrl+L → Ctrl+C."""
    if not _focus_browser():
        return "Could not find a Firefox window."
    time.sleep(0.2)

    try:
        # Focus address bar, select all, copy
        _browser_key("ctrl+l")
        time.sleep(0.2)
        _browser_key("ctrl+a")
        time.sleep(0.1)
        _browser_key("ctrl+c")
        time.sleep(0.2)

        # Read clipboard to get URL
        try:
            import pyperclip
            url = pyperclip.paste().strip()
        except Exception:
            url = ""

        # Get title from the tab
        import subprocess
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True, text=True, timeout=5,
        )
        title = result.stdout.strip()

        if url:
            return f"URL: {url}\nTitle: {title or '(unknown)'}"
        return f"Title: {title or '(unknown)'}"
    except Exception as e:
        return f"Could not get page info: {e}"


@tool(
    name="browser_search",
    description="Search the web using Google or Wikipedia. Opens results in a new tab.",
    params={
        "query": {"type": "string", "description": "The search query"},
        "engine": {"type": "string", "description": "Search engine: 'google' (default) or 'wikipedia'", "default": "google"},
    },
    required=["query"],
)
def browser_search(query: str, engine: str = "google") -> str:
    """Search the web — opens a new tab with search results."""
    if engine == "wikipedia":
        url = f"https://en.wikipedia.org/wiki/{quote(query.replace(' ', '_'))}"
    else:
        url = f"https://www.google.com/search?q={quote(query)}"
    try:
        webbrowser.open(url, new=2)
        return f"Searched '{query}' on {engine}."
    except Exception as e:
        return f"Failed to search: {e}"


@tool(
    name="browser_scroll",
    description="Scroll the browser page up or down by a number of page-lengths.",
    params={
        "direction": {"type": "string", "description": "'down' or 'up'", "enum": ["down", "up"]},
        "pages": {"type": "integer", "description": "Number of page-lengths to scroll (default 1)", "default": 1},
    },
    required=["direction"],
)
def browser_scroll(direction: str = "down", pages: int = 1) -> str:
    """Scroll the page using Page Down / Page Up keys sent to Firefox."""
    key = "Page_Down" if direction == "down" else "Page_Up"
    for _ in range(pages):
        if not _browser_key(key):
            try:
                pyautogui.press(key.lower())
            except Exception as e:
                return f"Failed to scroll: {e}"
        time.sleep(0.1)
    return f"Scrolled {direction} {pages} page(s)."


@tool(
    name="browser_click_link",
    description="Click a link on the current page by searching for visible text."
               " Uses Ctrl+F to find the text, then clicks the link.",
    params={
        "text": {"type": "string", "description": "The visible text of the link to click (partial match OK)"},
    },
    required=["text"],
)
def browser_click_link(text: str) -> str:
    """Find visible text on a page using Ctrl+F, then click the link."""
    if not _focus_browser():
        return "Could not find a Firefox window."
    time.sleep(0.2)

    # Use Ctrl+F to find and highlight the text, then press Enter to click
    try:
        _browser_key("ctrl+f")
        time.sleep(0.3)
        _browser_type(text)
        time.sleep(0.3)
        _browser_key("Escape")
        time.sleep(0.1)

        # Click the highlighted link
        _browser_key("Return")
        return f"Clicked link with text '{text}'."
    except Exception as e:
        return f"Failed to click link: {e}"


@tool(
    name="browser_fill_form",
    description="Fill in a form field on the current page. Finds the field by label text,"
               " types the value, then optionally submits.",
    params={
        "field_label": {"type": "string", "description": "The label text of the field to fill (e.g. 'Email', 'Search')"},
        "value": {"type": "string", "description": "The value to type into the field"},
        "submit": {"type": "boolean", "description": "If true, presses Tab then Enter after filling (default false)", "default": False},
    },
    required=["field_label", "value"],
)
def browser_fill_form(field_label: str, value: str, submit: bool = False) -> str:
    """Find a form field by label text, fill it, and optionally submit."""
    if not _focus_browser():
        return "Could not find a Firefox window."
    time.sleep(0.2)

    try:
        _browser_key("ctrl+f")
        time.sleep(0.3)
        _browser_type(field_label)
        time.sleep(0.3)
        _browser_key("Escape")
        time.sleep(0.1)
        _browser_key("Escape")  # close find bar
        time.sleep(0.1)

        # Tab to the field (it should be highlighted/highlighted adjacent)
        _browser_key("Tab")
        time.sleep(0.1)

        # Select all and type the value
        _browser_key("ctrl+a")
        time.sleep(0.1)
        _browser_type(value)
        time.sleep(0.1)

        if submit:
            _browser_key("Tab")
            time.sleep(0.1)
            _browser_key("Return")
            return f"Filled '{field_label}' with '{value}' and submitted."
        return f"Filled '{field_label}' with '{value}'."
    except Exception as e:
        return f"Failed to fill form: {e}"
