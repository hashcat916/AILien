"""Browser automation tools for opening URLs and controlling the active browser."""
import html
import re
import subprocess
import time
import webbrowser
from urllib.parse import urlparse

import pyautogui
import requests

from tools import tool


# ---------------------------------------------------------------------------
# Helpers: send keystrokes directly to the browser window so they work
# even when the terminal (or another window) has focus.
# ---------------------------------------------------------------------------

def _browser_wid() -> str | None:
    """Get the first Firefox window ID. Returns None if not found."""
    try:
        r = subprocess.run(
            ["xdotool", "search", "--class", "firefox"],
            capture_output=True, text=True, timeout=5,
        )
        wids = r.stdout.strip().split("\n")
        return wids[0] if wids[0] else None
    except Exception:
        return None


def _browser_key(*keys: str) -> bool:
    """Send keystrokes to the Firefox window (doesn't steal focus)."""
    wid = _browser_wid()
    if not wid:
        return False
    try:
        subprocess.run(
            ["xdotool", "key", "--window", wid, *keys],
            capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


def _browser_type(text: str) -> bool:
    """Type text into the Firefox window."""
    wid = _browser_wid()
    if not wid:
        return False
    try:
        subprocess.run(
            ["xdotool", "type", "--window", wid, text],
            capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


def _focus_browser() -> bool:
    """Bring Firefox to the foreground and focus it."""
    wid = _browser_wid()
    if not wid:
        return False
    try:
        subprocess.run(
            ["xdotool", "windowactivate", "--sync", wid],
            capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


@tool(
    name="open_url",
    description="Open a URL in the system's default web browser. Use this to open websites, search results, or web applications.",
    params={
        "url": {"type": "string", "description": "The URL to open, e.g. 'https://google.com'"},
        "new_window": {"type": "boolean", "description": "If true, opens in a new window instead of a new tab (default false)", "default": False},
    },
    required=["url"],
)
def open_url(url: str, new_window: bool = False) -> str:
    """Open a URL in the default browser."""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return f"Refused to open non-HTTP URL: {url}"

    try:
        if new_window:
            webbrowser.open(url, new=1)
        else:
            webbrowser.open(url, new=2)
        return f"Opened {url} in default browser."
    except Exception as e:
        return f"Failed to open {url}: {e}"


@tool(
    name="browser_navigate",
    description="Navigate the Firefox browser to a new URL. This focuses Firefox, types in the address bar, and presses Enter.",
    params={
        "url": {"type": "string", "description": "The URL to navigate to"},
    },
    required=["url"],
)
def browser_navigate(url: str) -> str:
    """Navigate Firefox to a URL — focuses the browser first so
    keyboard shortcuts land in the right window."""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return f"Refused to navigate to non-HTTP URL: {url}"

    # Focus Firefox (needed for address bar interaction)
    if not _focus_browser():
        try:
            webbrowser.open(url, new=2)
            return f"Opened {url} in default browser."
        except Exception as e:
            return f"Failed to open {url}: {e}"

    time.sleep(0.3)

    # Ctrl+L → address bar, Ctrl+A → select all, type URL, Enter
    _browser_key("ctrl+l")
    time.sleep(0.2)
    _browser_key("ctrl+a")
    time.sleep(0.1)
    _browser_type(url)
    time.sleep(0.1)
    _browser_key("Return")
    return f"Navigated to {url}"


@tool(
    name="browser_find",
    description="Open the find-in-page dialog and search for text on the current webpage.",
    params={
        "text": {"type": "string", "description": "Text to search for on the page"},
    },
    required=["text"],
)
def browser_find(text: str) -> str:
    if _focus_browser():
        _browser_key("ctrl+f")
        time.sleep(0.2)
        _browser_type(text)
        time.sleep(0.1)
        _browser_key("Escape")
        return f"Finding '{text}' on current page."
    # Fallback
    try:
        pyautogui.hotkey("ctrl", "f")
        pyautogui.typewrite(text, interval=0.01)
        pyautogui.press("esc")
        return f"Finding '{text}' on current page."
    except Exception as e:
        return f"Failed to find text: {e}"


@tool(
    name="browser_new_tab",
    description="Open a new browser tab in the active Firefox window.",
    params={},
    required=[],
)
def browser_new_tab() -> str:
    if _browser_key("ctrl+t"):
        return "Opened a new Firefox tab."
    try:
        pyautogui.hotkey("ctrl", "t")
        return "Opened a new browser tab."
    except Exception as e:
        return f"Failed to open new tab: {e}"


@tool(
    name="browser_close_tab",
    description="Close the current browser tab.",
    params={},
    required=[],
)
def browser_close_tab() -> str:
    if _browser_key("ctrl+w"):
        return "Closed current tab."
    try:
        pyautogui.hotkey("ctrl", "w")
        return "Closed current browser tab."
    except Exception as e:
        return f"Failed to close tab: {e}"


@tool(
    name="browser_go_back",
    description="Navigate back to the previous page in the browser history.",
    params={},
    required=[],
)
def browser_go_back() -> str:
    if _browser_key("alt+Left"):
        return "Navigated back."
    try:
        pyautogui.hotkey("alt", "left")
        return "Navigated back."
    except Exception as e:
        return f"Failed to go back: {e}"


@tool(
    name="browser_go_forward",
    description="Navigate forward to the next page in the browser history.",
    params={},
    required=[],
)
def browser_go_forward() -> str:
    if _browser_key("alt+Right"):
        return "Navigated forward."
    try:
        pyautogui.hotkey("alt", "right")
        return "Navigated forward."
    except Exception as e:
        return f"Failed to go forward: {e}"


@tool(
    name="browser_refresh",
    description="Refresh/reload the current webpage.",
    params={},
    required=[],
)
def browser_refresh() -> str:
    if _browser_key("F5"):
        return "Page refreshed."
    try:
        pyautogui.press("f5")
        return "Page refreshed."
    except Exception as e:
        return f"Failed to refresh: {e}"


@tool(
    name="browser_switch_tab",
    description="Switch to the next or previous browser tab.",
    params={
        "direction": {"type": "string", "description": "'next' or 'previous' tab", "enum": ["next", "previous"]},
    },
    required=["direction"],
)
def browser_switch_tab(direction: str) -> str:
    if direction == "next":
        if _browser_key("ctrl+Tab"):
            return "Switched to next tab."
    else:
        if _browser_key("ctrl+shift+Tab"):
            return "Switched to previous tab."
    try:
        if direction == "next":
            pyautogui.hotkey("ctrl", "tab")
        else:
            pyautogui.hotkey("ctrl", "shift", "tab")
        return f"Switched to {direction} tab."
    except Exception as e:
        return f"Failed to switch tab: {e}"


@tool(
    name="get_webpage_text",
    description="Fetch a webpage URL and extract the readable text content. This does NOT open a browser — it downloads the page directly and returns the text. Use this to read articles, documentation, or search results without rendering.",
    params={
        "url": {"type": "string", "description": "The URL to fetch"},
        "max_chars": {"type": "integer", "description": "Maximum characters to return (default 8000)", "default": 8000},
    },
    required=["url"],
)
def get_webpage_text(url: str, max_chars: int = 8000) -> str:
    """Fetch a webpage and extract readable text using requests + regex."""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return f"Refused to fetch non-HTTP URL: {url}"

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        html_text = resp.text

        # Decode HTML entities
        html_text = html.unescape(html_text)

        # Remove script and style blocks
        html_text = re.sub(r"<script[^>]*>.*?</script>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
        html_text = re.sub(r"<style[^>]*>.*?</style>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
        html_text = re.sub(r"<nav[^>]*>.*?</nav>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
        html_text = re.sub(r"<header[^>]*>.*?</header>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
        html_text = re.sub(r"<footer[^>]*>.*?</footer>", "", html_text, flags=re.DOTALL | re.IGNORECASE)

        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else "No title"

        # Preserve link URLs before stripping tags
        def _link_replacer(m: re.Match) -> str:
            href = m.group(1) or ""
            link_text = m.group(2) or ""
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                return f"{link_text} [{href}]"
            return link_text

        html_text = re.sub(
            r'<a[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            _link_replacer,
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Replace tags with newlines for readability
        text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<li>", "\n• ", text, flags=re.IGNORECASE)
        text = re.sub(r"<h[1-6][^>]*>", "\n\n# ", text, flags=re.IGNORECASE)
        text = re.sub(r"</h[1-6]>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)

        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = text.strip()

        # Truncate if too long
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n... [{len(text) - max_chars} more characters truncated]"

        return f"Title: {title}\nURL: {url}\n\n{text}"
    except requests.Timeout:
        return f"Request timed out fetching {url}"
    except requests.RequestException as e:
        return f"Failed to fetch {url}: {e}"
    except Exception as e:
        return f"Error processing {url}: {e}"
