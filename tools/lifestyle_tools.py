"""Lifestyle tools — package tracking, recipe finder, weather alerts, PDF toolkit, git assistant."""

import logging
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from tools import tool

logger = logging.getLogger("agent")


# ===================================================================
# 📦 PACKAGE TRACKING
# ===================================================================

_CARRIERS = {
    "ups": {
        "name": "UPS",
        "url": "https://www.ups.com/track?tracknum={tracking}",
        "regex": None,  # Will parse by fetching page
    },
    "fedex": {
        "name": "FedEx",
        "url": "https://www.fedex.com/fedextrack/?trknbr={tracking}",
        "regex": None,
    },
    "usps": {
        "name": "USPS",
        "url": "https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking}",
        "regex": None,
    },
    "dhl": {
        "name": "DHL",
        "url": "https://www.dhl.com/en/express/tracking.html?AWB={tracking}&brand=DHL",
        "regex": None,
    },
}


@tool(
    name="track_package",
    description="Track a package by carrier and tracking number. Opens the carrier's tracking page and tries to fetch basic status.",
    params={
        "carrier": {"type": "string", "description": "Carrier name: 'ups', 'fedex', 'usps', 'dhl'"},
        "tracking_number": {"type": "string", "description": "The tracking number provided by the carrier"},
    },
    required=["carrier", "tracking_number"],
)
def track_package(carrier: str, tracking_number: str) -> str:
    carrier = carrier.lower().strip()
    if carrier not in _CARRIERS:
        return f"Unknown carrier '{carrier}'. Supported: {', '.join(_CARRIERS.keys())}."

    info = _CARRIERS[carrier]
    tracking_url = info["url"].format(tracking=tracking_number)

    # Try to fetch a simple status from the carrier's tracking page
    page_text = ""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(tracking_url, headers=headers, timeout=15)
        if resp.ok:
            page_text = resp.text[:5000]
    except Exception as e:
        logger.debug("Package tracking fetch failed: %s", e)

    # Try to extract status info (works for UPS/USPS simple pages)
    status = "Status information could not be retrieved automatically."
    if page_text:
        # Common status keywords to look for
        status_keywords = [
            "delivered", "in transit", "out for delivery", "processing",
            "picked up", "label created", "shipment received", "on the way",
            "arrived at facility", "departed facility", "exception",
        ]
        found = []
        lower_text = page_text.lower()
        for kw in status_keywords:
            if kw in lower_text:
                found.append(kw.title())

        if found:
            status = " | ".join(found[:3])
        else:
            # Try to find any date-like patterns (tracking updates often have dates)
            dates = re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', page_text)
            if dates:
                status = f"Last update date found: {dates[0]}"

    # Also open the tracking page in the default browser
    try:
        import webbrowser
        webbrowser.open(tracking_url)
        browser_msg = "\nOpened tracking page in your browser."
    except Exception:
        browser_msg = ""

    return (
        f"📦 {info['name']} — {tracking_number}\n"
        f"  Status: {status}{browser_msg}\n"
        f"  Full tracking: {tracking_url}"
    )


# ===================================================================
# 🍳 RECIPE FINDER
# ===================================================================

@tool(
    name="find_recipes",
    description="Search for recipes by ingredients or dish name. Finds recipes from the web with details.",
    params={
        "query": {"type": "string", "description": "What you want to cook, e.g. 'chicken and rice', 'pasta with tomatoes'"},
        "max_results": {"type": "integer", "description": "Max recipes to return (default 5)", "default": 5},
    },
    required=["query"],
)
def find_recipes(query: str, max_results: int = 5) -> str:
    """Search for recipes using DuckDuckGo HTML search, no API key needed."""
    try:
        from urllib.parse import quote
        search_url = f"https://html.duckduckgo.com/html/?q={quote(query + ' recipe')}"

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(search_url, headers=headers, timeout=15)

        if not resp.ok:
            # Fallback: just give a search URL
            search_url = f"https://duckduckgo.com/?q={quote(query + ' recipe')}"
            return (
                f"🔍 Recipes for: {query}\n\n"
                f"Open this search in your browser:\n"
                f"  {search_url}"
            )

        # Parse HTML results
        from html.parser import HTMLParser

        class ResultParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.results = []
                self._in_result = False
                self._in_link = False
                self._current = {"title": "", "url": "", "snippet": ""}
                self._depth = 0
                self._snippet_capture = False

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag == "a" and "result__a" in attrs_dict.get("class", ""):
                    self._current["url"] = attrs_dict.get("href", "")
                    self._in_link = True
                if tag == "a" and self._in_link and "class" not in attrs_dict:
                    self._in_link = True
                if tag == "a" and "result__snippet" in attrs_dict.get("class", ""):
                    self._snippet_capture = True

            def handle_data(self, data):
                if self._in_link:
                    self._current["title"] += data
                if self._snippet_capture:
                    self._current["snippet"] += data

            def handle_endtag(self, tag):
                if tag == "a" and self._in_link:
                    if self._current["title"].strip():
                        self.results.append(dict(self._current))
                    self._current = {"title": "", "url": "", "snippet": ""}
                    self._in_link = False
                    self._snippet_capture = False

        parser = ResultParser()
        parser.feed(resp.text)

        # Filter for recipe-like results
        recipes = []
        for r in parser.results:
            title = r["title"].strip()
            url = r["url"].strip()
            # Clean DuckDuckGo redirect URL
            if "uddg=" in url:
                from urllib.parse import unquote, parse_qs, urlparse
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                actual_url = unquote(qs.get("uddg", [""])[0])
                if actual_url:
                    url = actual_url
            snippet = r.get("snippet", "").strip()
            if title and url and not url.startswith("javascript:"):
                recipes.append((title, url, snippet))
                if len(recipes) >= max_results:
                    break

        if recipes:
            lines = [f"🍳 Recipes for: {query}", ""]
            for i, (title, url, snippet) in enumerate(recipes, 1):
                lines.append(f"  {i}. {title}")
                lines.append(f"     {url}")
                if snippet:
                    lines.append(f"     {snippet[:120]}...")
                lines.append("")
            return "\n".join(lines)

        # Fallback
        search_url = f"https://duckduckgo.com/?q={quote(query + ' recipe')}"
        return (
            f"🔍 Could not parse recipe results. Try searching manually:\n"
            f"  {search_url}"
        )

    except Exception as e:
        from urllib.parse import quote
        search_url = f"https://duckduckgo.com/?q={quote(query + ' recipe')}"
        return (
            f"Recipe search error: {e}\n\n"
            f"Try this search:\n"
            f"  {search_url}"
        )


# ===================================================================
# 🌤️ WEATHER ALERTS
# ===================================================================

_weather_alerts_active = False
_weather_alert_thread: threading.Thread | None = None
_weather_alert_stop = threading.Event()


def _weather_alert_worker(location: str, interval_minutes: int, callback) -> None:
    """Background thread that periodically checks weather and alerts on severe conditions."""
    last_check = datetime.min

    while not _weather_alert_stop.is_set():
        now = datetime.now()
        if (now - last_check).total_seconds() < interval_minutes * 60:
            _weather_alert_stop.wait(30)
            continue

        last_check = now
        try:
            from urllib.parse import quote
            url = f"https://wttr.in/{quote(location)}?format=%C+%t+%w+%p&lang=en"
            resp = requests.get(url, timeout=10)

            if resp.ok:
                text = resp.text.strip().lower()
                # Check for severe conditions
                alerts = []
                if any(kw in text for kw in ["thunderstorm", "thunder", "lightning"]):
                    alerts.append("⚡ Thunderstorms detected")
                if any(kw in text for kw in ["tornado", "waterspout"]):
                    alerts.append("🌪️ Tornado warning!")
                if any(kw in text for kw in ["hurricane", "typhoon", "cyclone"]):
                    alerts.append("🌀 Hurricane/cyclone conditions")
                if any(kw in text for kw in ["blizzard", "heavy snow", "snowstorm"]):
                    alerts.append("❄️ Blizzard/heavy snow")
                if any(kw in text for kw in ["extreme", "dangerous", "advisory"]):
                    alerts.append("⚠️ Extreme weather advisory")
                if any(kw in text for kw in ["fog", "dense fog"]):
                    alerts.append("🌫️ Dense fog")
                # High wind
                wind_match = re.search(r'(\d+)\s*(km/h|mph)', text)
                if wind_match:
                    wind_speed = int(wind_match.group(1))
                    unit = wind_match.group(2)
                    if (unit == "km/h" and wind_speed > 50) or (unit == "mph" and wind_speed > 31):
                        alerts.append(f"💨 High wind: {wind_match.group(0)}")

                if alerts:
                    msg = f"📍 {location}: {' · '.join(alerts)}. {resp.text.strip()}"
                    try:
                        callback(msg)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("Weather alert check failed: %s", e)


@tool(
    name="start_weather_alerts",
    description="Start proactive severe weather alerts for a location. Checks every N minutes and notifies you of severe conditions.",
    params={
        "location": {"type": "string", "description": "City name or 'auto' for your location", "default": "auto"},
        "interval_minutes": {"type": "integer", "description": "Check interval in minutes (default 60)", "default": 60},
    },
    required=[],
)
def start_weather_alerts(location: str = "auto", interval_minutes: int = 60) -> str:
    global _weather_alerts_active, _weather_alert_thread, _weather_alert_stop

    if _weather_alerts_active:
        return "Weather alerts are already running."

    _weather_alert_stop.clear()
    _weather_alerts_active = True

    def _notify(msg: str) -> None:
        """Print weather alert to console."""
        from utils.helpers import notify, console
        console.print(f"\n  [bold yellow]🌤️ Weather Alert:[/bold yellow] {msg}")
        try:
            notify("🌤️ Weather Alert", msg)
        except Exception:
            pass

    _weather_alert_thread = threading.Thread(
        target=_weather_alert_worker,
        args=(location, max(15, interval_minutes), _notify),
        daemon=True,
    )
    _weather_alert_thread.start()

    return (
        f"🌤️ Weather alerts started for '{location}'. "
        f"Checking every {interval_minutes} minutes. "
        f"Use stop_weather_alerts to turn off."
    )


@tool(
    name="stop_weather_alerts",
    description="Stop the proactive severe weather alerts.",
    params={},
    required=[],
)
def stop_weather_alerts() -> str:
    global _weather_alerts_active, _weather_alert_stop

    if not _weather_alerts_active:
        return "Weather alerts are not running."

    _weather_alert_stop.set()
    _weather_alerts_active = False
    return "🌤️ Weather alerts stopped."


# ===================================================================
# 📄 PDF TOOLKIT
# ===================================================================

@tool(
    name="pdf_merge",
    description="Merge multiple PDF files into one. Provide a list of file paths and an output path.",
    params={
        "files": {"type": "string", "description": "Comma-separated list of PDF file paths to merge"},
        "output": {"type": "string", "description": "Output file path (e.g. 'merged.pdf')", "default": "merged.pdf"},
    },
    required=["files"],
)
def pdf_merge(files: str, output: str = "merged.pdf") -> str:
    try:
        from pypdf import PdfWriter

        file_list = [f.strip() for f in files.split(",")]
        writer = PdfWriter()

        pages_total = 0
        errors = []
        for fpath in file_list:
            p = Path(fpath).expanduser()
            if not p.exists():
                errors.append(f"  File not found: {fpath}")
                continue
            try:
                writer.append(str(p))
                import pypdf
                reader = pypdf.PdfReader(str(p))
                pages_total += len(reader.pages)
            except Exception as e:
                errors.append(f"  Could not read {fpath}: {e}")

        if pages_total == 0:
            return "No valid PDF files to merge."

        output_path = Path(output).expanduser()
        with open(output_path, "wb") as f:
            writer.write(f)

        result = f"📄 Merged {len(file_list) - len(errors)} PDFs into {output_path} ({pages_total} pages total)."
        if errors:
            result += "\n\nErrors:\n" + "\n".join(errors)
        return result
    except ImportError:
        return "PDF tools require pypdf. Install with: pip install pypdf"
    except Exception as e:
        return f"PDF merge failed: {e}"


@tool(
    name="pdf_split",
    description="Split a PDF into individual pages. Each page becomes a separate PDF file.",
    params={
        "file": {"type": "string", "description": "Path to the PDF file to split"},
        "output_dir": {"type": "string", "description": "Output directory for split pages (default: same as input, named 'pages')", "default": ""},
    },
    required=["file"],
)
def pdf_split(file: str, output_dir: str = "") -> str:
    try:
        from pypdf import PdfWriter, PdfReader

        p = Path(file).expanduser()
        if not p.exists():
            return f"File not found: {f}"

        reader = PdfReader(str(p))
        total = len(reader.pages)

        out_dir = Path(output_dir).expanduser() if output_dir else (p.parent / f"{p.stem}_pages")
        out_dir.mkdir(parents=True, exist_ok=True)

        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            out_path = out_dir / f"{p.stem}_page_{i + 1:03d}.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)

        return f"📄 Split {total} pages into {out_dir}/"
    except ImportError:
        return "PDF tools require pypdf. Install with: pip install pypdf"
    except Exception as e:
        return f"PDF split failed: {e}"


@tool(
    name="pdf_extract_text",
    description="Extract text from a PDF file.",
    params={
        "file": {"type": "string", "description": "Path to the PDF file"},
    },
    required=["file"],
)
def pdf_extract_text(file: str) -> str:
    try:
        from pypdf import PdfReader

        p = Path(file).expanduser()
        if not p.exists():
            return f"File not found: {file}"

        reader = PdfReader(str(p))
        pages_text = []
        total = len(reader.pages)

        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(f"--- Page {i + 1} ---\n{text.strip()[:1000]}")

        if not pages_text:
            return f"No extractable text found in '{p.name}'. The PDF may contain only scanned images."

        summary = f"📄 Extracted text from {p.name} ({total} pages, {len(pages_text)} with content):\n\n"
        return summary + "\n\n".join(pages_text[:10])
    except ImportError:
        return "PDF tools require pypdf. Install with: pip install pypdf"
    except Exception as e:
        return f"PDF text extraction failed: {e}"


# ===================================================================
# 🐙 GIT ASSISTANT
# ===================================================================

_GIT_SAFE = True  # Can be toggled off for destructive operations


def _run_git(args: list[str], cwd: str | None = None) -> tuple[bool, str]:
    """Run a git command safely. Returns (success, output)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd or os.getcwd(),
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "Git is not installed or not in PATH."
    except subprocess.TimeoutExpired:
        return False, "Git command timed out."
    except Exception as e:
        return False, str(e)


def _find_git_root(path: str | None = None) -> str | None:
    """Find the git root of the current or specified directory."""
    success, output = _run_git(["rev-parse", "--show-toplevel"], cwd=path)
    if success:
        return output
    return None


@tool(
    name="git_status",
    description="Show the current git status — branch, uncommitted changes, and sync status.",
    params={
        "path": {"type": "string", "description": "Optional path to a git repository (defaults to current directory)", "default": ""},
    },
    required=[],
)
def git_status(path: str = "") -> str:
    cwd = Path(path).expanduser() if path else None
    root = _find_git_root(cwd)
    if not root:
        return "Not a git repository (or no git found)."

    # Branch
    ok, branch = _run_git(["branch", "--show-current"], cwd=root)
    branch = branch or "(detached HEAD)"

    # Status
    ok, status = _run_git(["status", "--short"], cwd=root)

    # Count commits ahead/behind
    ok, ahead_behind = _run_git(["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], cwd=root)
    ahead = behind = 0
    if ok and ahead_behind:
        parts = ahead_behind.split()
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])

    # Last commit
    ok, last_commit = _run_git(["log", "-1", "--format=%h %s (%ar)"], cwd=root)

    lines = [f"🐙 Git Status — {Path(root).name}", ""]
    lines.append(f"  Branch:     {branch}")
    if ahead or behind:
        parts = []
        if ahead:
            parts.append(f"{ahead} ahead")
        if behind:
            parts.append(f"{behind} behind")
        lines.append(f"  Remote:     {', '.join(parts)}")
    lines.append("")

    if status:
        # Parse into staged/unstaged/untracked
        staged = []
        unstaged = []
        untracked = []
        for line in status.split("\n"):
            if line.startswith("??"):
                untracked.append(line[3:])
            elif line[0] != " ":
                staged.append(line[3:])
            else:
                unstaged.append(line[3:])

        if staged:
            lines.append(f"  Staged: {len(staged)} file(s)")
            for s in staged[:5]:
                lines.append(f"    · {s}")
        if unstaged:
            lines.append(f"  Modified: {len(unstaged)} file(s)")
            for s in unstaged[:5]:
                lines.append(f"    · {s}")
        if untracked:
            lines.append(f"  Untracked: {len(untracked)} file(s)")
            for s in untracked[:5]:
                lines.append(f"    · {s}")
    else:
        lines.append("  ✓ Clean working tree")

    if last_commit:
        lines.append("")
        lines.append(f"  Last commit: {last_commit}")

    return "\n".join(lines)


@tool(
    name="git_commit",
    description="Stage all changes and commit with a message. Shows a diff preview first.",
    params={
        "message": {"type": "string", "description": "Commit message describing the changes"},
        "path": {"type": "string", "description": "Optional path to a git repository", "default": ""},
    },
    required=["message"],
)
def git_commit(message: str, path: str = "") -> str:
    cwd = Path(path).expanduser() if path else None
    root = _find_git_root(cwd)
    if not root:
        return "Not a git repository."

    # Show diff preview first
    ok, diff = _run_git(["diff", "--stat"], cwd=root)
    if diff:
        diff_preview = f"Changes:\n{diff}"
    else:
        ok, diff = _run_git(["diff", "--cached", "--stat"], cwd=root)
        diff_preview = f"Staged changes:\n{diff}" if diff else "No changes to commit."

    if not diff and not diff_preview:
        # Check for untracked
        ok, untracked = _run_git(["ls-files", "--others", "--exclude-standard"], cwd=root)
        if untracked:
            diff_preview = f"Untracked files: {untracked}"

    # Stage all
    ok, _ = _run_git(["add", "-A"], cwd=root)
    if not ok:
        return "Failed to stage changes."

    # Commit
    ok, output = _run_git(["commit", "-m", message], cwd=root)
    if ok:
        return (
            f"✅ Committed:\n"
            f"  {message}\n\n"
            f"{diff_preview}"
        )
    return f"Commit failed: {output}"


@tool(
    name="git_push",
    description="Push committed changes to the remote repository.",
    params={
        "branch": {"type": "string", "description": "Branch to push (defaults to current branch)", "default": ""},
        "path": {"type": "string", "description": "Optional path to a git repository", "default": ""},
        "force": {"type": "boolean", "description": "Force push (use with caution!)", "default": False},
    },
    required=[],
)
def git_push(branch: str = "", path: str = "", force: bool = False) -> str:
    cwd = Path(path).expanduser() if path else None
    root = _find_git_root(cwd)
    if not root:
        return "Not a git repository."

    if not branch:
        ok, branch = _run_git(["branch", "--show-current"], cwd=root)
        if not ok or not branch:
            return "Could not determine current branch."

    # Check for unpushed commits
    ok, ahead = _run_git(["rev-list", "--count", "@{upstream}..HEAD"], cwd=root)
    commits_ahead = int(ahead) if ok and ahead else 0

    cmd = ["push", "origin", branch]
    if force:
        cmd.append("--force")

    ok, output = _run_git(cmd, cwd=root)
    if ok:
        msg = f"✅ Pushed {branch} to origin"
        if commits_ahead:
            msg += f" ({commits_ahead} commit{'s' if commits_ahead != 1 else ''})"
        return msg
    return f"Push failed: {output}"


@tool(
    name="git_pull",
    description="Pull the latest changes from the remote repository.",
    params={
        "path": {"type": "string", "description": "Optional path to a git repository", "default": ""},
        "rebase": {"type": "boolean", "description": "Use rebase instead of merge", "default": False},
    },
    required=[],
)
def git_pull(path: str = "", rebase: bool = False) -> str:
    cwd = Path(path).expanduser() if path else None
    root = _find_git_root(cwd)
    if not root:
        return "Not a git repository."

    ok, branch = _run_git(["branch", "--show-current"], cwd=root)
    branch = branch or "?"

    cmd = ["pull"]
    if rebase:
        cmd.append("--rebase")

    ok, output = _run_git(cmd, cwd=root)
    if ok:
        return f"✅ Pulled latest changes into {branch}"
    return f"Pull failed: {output}"


@tool(
    name="git_log",
    description="Show recent git commit history.",
    params={
        "count": {"type": "integer", "description": "Number of commits to show (default 10)", "default": 10},
        "path": {"type": "string", "description": "Optional path to a git repository", "default": ""},
    },
    required=[],
)
def git_log(count: int = 10, path: str = "") -> str:
    cwd = Path(path).expanduser() if path else None
    root = _find_git_root(cwd)
    if not root:
        return "Not a git repository."

    ok, output = _run_git(
        ["log", f"-{min(count, 50)}", "--format=%h %s (%ar) — %an", "--stat=30"],
        cwd=root,
    )
    if ok:
        repo_name = Path(root).name
        return f"🐙 Recent commits — {repo_name}\n\n{output}"
    return f"Git log failed: {output}"
