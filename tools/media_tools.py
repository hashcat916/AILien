"""Media playback tools — local files, YouTube, and URL playback with controls."""

import logging
import os
import signal
import shutil
import subprocess
import time
from pathlib import Path

from tools import tool

logger = logging.getLogger("agent")

# Common media directories to search
MEDIA_DIRS = [
    Path.home() / "Music",
    Path.home() / "Videos",
    Path.home() / "Movies",
    Path.home() / "Downloads",
]

# Common media file extensions
MEDIA_EXTENSIONS = {
    ".mp3", ".flac", ".wav", ".aac", ".ogg", ".wma", ".m4a", ".opus",
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    ".mpeg", ".mpg", ".3gp", ".ts", ".mts", ".m2ts",
}

# Preferred players in order
PLAYERS = ["celluloid", "vlc", "mpv", "ffplay", "xdg-open"]

# Track active player processes for control
_active_players: dict[str, dict] = {}


def _find_player() -> str | None:
    for player in PLAYERS:
        path = shutil.which(player)
        if path:
            return path
    return None


def _cleanup_players() -> None:
    """Remove dead entries from _active_players."""
    for name, info in list(_active_players.items()):
        proc = info.get("process")
        if proc and proc.poll() is not None:
            del _active_players[name]


def _search_media(query: str, max_results: int = 20) -> list[Path]:
    query_lower = query.lower()
    matches: list[Path] = []
    for media_dir in MEDIA_DIRS:
        if not media_dir.is_dir():
            continue
        try:
            for f in media_dir.rglob("*"):
                if len(matches) >= max_results:
                    break
                if not f.is_file():
                    continue
                if f.suffix.lower() not in MEDIA_EXTENSIONS:
                    continue
                if query_lower in f.stem.lower():
                    matches.append(f)
        except PermissionError:
            continue
    return matches


# ---------------------------------------------------------------------------
# Local media
# ---------------------------------------------------------------------------


@tool(
    name="play_media",
    description="Search for and play a local movie, music file, or video by name.",
    params={
        "query": {
            "type": "string",
            "description": "Name or partial name of the media file (e.g. 'feel good', 'avatar')",
        },
        "player": {
            "type": "string",
            "description": "Player: 'default' (auto), 'celluloid', 'vlc', 'mpv', or 'ffplay'",
            "default": "default",
        },
    },
    required=["query"],
)
def play_media(query: str, player: str = "default") -> str:
    if not query.strip():
        return "Please provide a search term."
    matches = _search_media(query)
    if not matches:
        for media_dir in MEDIA_DIRS:
            if not media_dir.is_dir():
                continue
            try:
                entries = list(media_dir.iterdir())
                if entries:
                    names = ", ".join(e.stem for e in entries[:20] if e.is_file() and e.suffix.lower() in MEDIA_EXTENSIONS)
                    return f"No media found matching '{query}'. Files in {media_dir.name}: {names}"
            except PermissionError:
                continue
        dirs = ", ".join(str(d) for d in MEDIA_DIRS if d.is_dir())
        return f"No media found matching '{query}'. Checked: {dirs}."
    target = matches[0]
    if len(matches) > 1:
        exact = [m for m in matches if m.stem.lower() == query.lower()]
        if exact:
            target = exact[0]
    return _launch_player(str(target), Path(target).name, target.stat().st_size)


@tool(
    name="list_media",
    description="List available media files in Music, Videos, Movies, and Downloads folders.",
    params={
        "directory": {"type": "string", "description": "'music', 'videos', 'downloads', or 'all'", "default": "all"},
        "max_results": {"type": "integer", "description": "Maximum files to show (default 30)", "default": 30},
    },
    required=[],
)
def list_media(directory: str = "all", max_results: int = 30) -> str:
    dirs_to_check: list[Path] = []
    dl = directory.lower()
    if dl in ("music", "audio", "songs"):
        dirs_to_check = [Path.home() / "Music"]
    elif dl in ("videos", "video", "movies", "movie"):
        dirs_to_check = [Path.home() / "Videos", Path.home() / "Movies"]
    elif dl in ("downloads", "dl"):
        dirs_to_check = [Path.home() / "Downloads"]
    else:
        dirs_to_check = MEDIA_DIRS
    results: list[str] = []
    for d in dirs_to_check:
        if not d.is_dir():
            continue
        try:
            for f in sorted(d.iterdir()):
                if len(results) >= max_results:
                    break
                if not f.is_file() or f.suffix.lower() not in MEDIA_EXTENSIONS:
                    continue
                size = f.stat().st_size / (1024 ** 2)
                kind = "🎵" if f.suffix.lower() in {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".opus"} else "🎬"
                results.append(f"{kind}  {f.stem:40s}  {size:6.0f} MB  ({d.name})")
        except PermissionError:
            continue
    if not results:
        dirs_str = ", ".join(str(d) for d in dirs_to_check if d.is_dir())
        return f"No media files found in {dirs_str}."
    header = f"{'Type':4}  {'Name':40s}  {'Size':>6}  {'Location'}\n{'─'*70}"
    return header + "\n" + "\n".join(results)


# ---------------------------------------------------------------------------
# Player management
# ---------------------------------------------------------------------------


def _launch_player(media_path: str, title: str, size_bytes: int | None = None) -> str:
    _cleanup_players()
    player_bin = _find_player()
    if not player_bin:
        return "No media player found. Install celluloid, vlc, or mpv."
    try:
        if "mpv" in player_bin:
            proc = subprocess.Popen(
                [player_bin, f"--title={title[:80]}", media_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp,
            )
            player_name = "mpv"
        elif "ffplay" in player_bin:
            proc = subprocess.Popen(
                ["nohup", player_bin, "-autoexit", "-window_title", title[:80], media_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp,
            )
            player_name = "ffplay"
        elif "celluloid" in player_bin:
            proc = subprocess.Popen(
                [player_bin, media_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            player_name = "celluloid"
        else:
            proc = subprocess.Popen(
                ["nohup", player_bin, media_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            player_name = Path(player_bin).name

        pid = proc.pid
        _active_players[player_name] = {"pid": pid, "process": proc, "title": title, "media": media_path, "started": time.time()}
        size_str = f" ({size_bytes / 1024**2:.0f} MB)" if size_bytes else ""
        return f"▶️ Now playing '{title}'{size_str} with {player_name} (PID {pid}).\n   Use player_control to pause/resume/stop."

    except Exception as e:
        return f"Failed to play media: {e}"


@tool(
    name="player_control",
    description="Control currently playing media: pause, resume, stop, or check status.",
    params={
        "action": {"type": "string", "description": "'pause', 'resume', 'stop', or 'status'", "enum": ["pause", "resume", "stop", "status"]},
        "player": {"type": "string", "description": "Player name to control (use 'status' to see active players)", "default": ""},
    },
    required=["action"],
)
def player_control(action: str, player: str = "") -> str:
    _cleanup_players()
    if action == "status":
        if not _active_players:
            return "No active players."
        lines = ["Active players:"]
        for name, info in list(_active_players.items()):
            proc = info.get("process")
            alive = proc and proc.poll() is None
            status = "▶️ Playing" if alive else "⏹️ Stopped"
            runtime = int(time.time() - info.get("started", time.time()))
            lines.append(f"  {status}  {name} (PID {info['pid']}) — {info['title'][:50]} (running {runtime}s)")
            if not alive:
                del _active_players[name]
        return "\n".join(lines)

    target_name = ""
    target: dict | None = None
    if player:
        target = _active_players.get(player)
        target_name = player
    else:
        for name, info in reversed(list(_active_players.items())):
            if info.get("process") and info["process"].poll() is None:
                target = info
                target_name = name
                break
    if not target:
        return "No active player found. Start playback first with play_media, play_youtube, or play_url."
    proc = target.get("process")
    if not proc or proc.poll() is not None:
        del _active_players[target_name]
        return f"Player '{target_name}' has already stopped."
    pid = target["pid"]
    try:
        if action == "pause":
            os.killpg(os.getpgid(pid), signal.SIGSTOP)
            return f"⏸️ Paused '{target['title']}'."
        elif action == "resume":
            os.killpg(os.getpgid(pid), signal.SIGCONT)
            return f"▶️ Resumed '{target['title']}'."
        elif action == "stop":
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            time.sleep(0.3)
            if proc.poll() is None:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            del _active_players[target_name]
            return f"⏹️ Stopped '{target['title']}'."
    except ProcessLookupError:
        del _active_players[target_name]
        return f"Player '{target_name}' has already exited."
    except Exception as e:
        return f"Failed to {action} player: {e}"


# ---------------------------------------------------------------------------
# YouTube search & playback
# ---------------------------------------------------------------------------


@tool(
    name="youtube_search",
    description="Search YouTube for videos matching a query.",
    params={"query": {"type": "string", "description": "Search query — song, topic, channel, etc."}},
    required=["query"],
)
def youtube_search(query: str) -> str:
    try:
        from brain.youtube import search as yt_search
        return yt_search(query)
    except Exception as exc:
        return f"YouTube search failed: {exc}"


def _search_youtube_videos(query: str, max_results: int = 5) -> list[dict]:
    try:
        from brain.youtube import _extract_with_ytdlp
        videos = _extract_with_ytdlp(f"ytsearch{max_results}:{query}")
        return videos
    except Exception:
        pass
    try:
        from yt_dlp import YoutubeDL
        from brain.youtube import _parse_duration as dur, _format_views as vws
        with YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True, "default_search": "ytsearch"}) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        entries = info.get("entries", []) if info else []
        results = []
        for entry in entries[:max_results]:
            if entry and entry.get("id"):
                results.append({
                    "title": entry.get("title", "Unknown"),
                    "url": f"https://youtube.com/watch?v={entry['id']}",
                    "video_id": entry["id"],
                    "duration": dur(entry.get("duration")),
                    "views": vws(entry.get("view_count")),
                    "channel": entry.get("channel", entry.get("uploader", "")),
                })
        return results
    except Exception:
        return []


@tool(
    name="play_youtube",
    description="Search YouTube and play the best matching video locally or in browser.",
    params={
        "query": {"type": "string", "description": "What to search for and play"},
        "player": {"type": "string", "description": "'auto' (local first) or 'browser'", "default": "auto", "enum": ["auto", "browser"]},
    },
    required=["query"],
)
def play_youtube(query: str, player: str = "auto") -> str:
    import webbrowser
    if not query.strip():
        return "Please provide a search term."
    videos = _search_youtube_videos(query)
    if not videos:
        return f"No YouTube results for '{query}'."
    target = videos[0]
    title, video_url = target["title"], target["url"]
    parts = [f"🎬 {title}"]
    if target.get("channel"):
        parts.append(f"   📺 {target['channel']}")
    if target.get("duration"):
        parts.append(f"   ⏱ {target['duration']}")
    if player == "browser":
        webbrowser.open(video_url)
        parts.append("   🌐 Opened in browser")
        return "\n".join(parts)
    local = _play_yt_with_player(video_url, title)
    if local:
        parts.append(f"   ▶️ {local}")
        return "\n".join(parts)
    webbrowser.open(video_url)
    parts.append("   🌐 Opened in browser")
    return "\n".join(parts)


@tool(
    name="youtube_trending",
    description="Show currently trending videos on YouTube.",
    params={},
    required=[],
)
def youtube_trending() -> str:
    try:
        from brain.youtube import trending as yt_trending
        return yt_trending()
    except Exception as exc:
        return f"Failed to fetch trending: {exc}"


@tool(
    name="youtube_transcript",
    description="Get the transcript/captions of a YouTube video. Optionally search within it.",
    params={
        "url": {"type": "string", "description": "YouTube video URL (or just the video ID like 'n61ULEU7CO0')"},
        "search": {"type": "string", "description": "Optional text to search for in transcript", "default": ""},
        "max_lines": {"type": "integer", "description": "Max lines to return (default 50)", "default": 50},
    },
    required=["url"],
)
def youtube_transcript(url: str, search: str = "", max_lines: int = 50) -> str:
    video_id = ""
    if "v=" in url:
        video_id = url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in url:
        video_id = url.split("youtu.be/")[-1].split("?")[0]
    if not video_id:
        return f"Could not extract video ID from: {url}"
    try:
        from yt_dlp import YoutubeDL
        import requests
        with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        title = info.get("title", "Unknown")
        caption_data = None
        for lang in ["en", "en-US", "en-GB", "a.en"]:
            if lang in info.get("subtitles", {}):
                caption_data = info["subtitles"][lang]
                break
        if not caption_data:
            for lang in ["en", "en-US", "en-GB", "a.en"]:
                if lang in info.get("automatic_captions", {}):
                    caption_data = info["automatic_captions"][lang]
                    break
        if not caption_data:
            return f"No captions available for '{title}'."
        caption_url = caption_data[-1].get("url", "")
        if not caption_url:
            return f"Could not retrieve caption URL."
        resp = requests.get(caption_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        lines = []
        for event in data.get("events", []):
            segs = event.get("segs", [])
            text = "".join(s.get("utf8", "") for s in segs)
            if text.strip():
                seconds = event.get("tStartMs", 0) / 1000
                m, s = divmod(int(seconds), 60)
                lines.append(f"[{m}:{s:02d}] {text.strip()}")
        if not lines:
            return f"No caption text found for '{title}'."
        result = [f"📝 Transcript: {title}\n"]
        if search:
            sl = search.lower()
            matched = [l for l in lines if sl in l.lower()]
            if not matched:
                return f"No matches for '{search}' in transcript."
            result.append(f"Found {len(matched)} matches:\n")
            result.extend(matched[:max_lines])
        else:
            result.extend(lines[:max_lines])
            if len(lines) > max_lines:
                result.append(f"\n... ({len(lines) - max_lines} more lines)")
        return "\n".join(result)
    except ImportError:
        return "yt-dlp is required: pip install yt-dlp"
    except Exception as exc:
        return f"Failed to get transcript: {exc}"


# ---------------------------------------------------------------------------
# URL playback (any URL)
# ---------------------------------------------------------------------------


def _play_yt_with_player(video_url: str, title: str) -> str | None:
    _cleanup_players()
    try:
        from yt_dlp import YoutubeDL
        with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "format": "best[height<=720]/best"}) as ydl:
            info = ydl.extract_info(video_url, download=False)
        stream_url = info.get("url")
        if not stream_url:
            return None
        player_bin = _find_player()
        if not player_bin:
            return None
        if "mpv" in player_bin:
            proc = subprocess.Popen(
                [player_bin, f"--title={title[:80]}", video_url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp,
            )
            pname = "mpv"
        else:
            proc = subprocess.Popen(
                ["nohup", player_bin, "-autoexit", "-window_title", title[:80], stream_url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp,
            )
            pname = Path(player_bin).name
        _active_players[pname] = {"pid": proc.pid, "process": proc, "title": title, "media": video_url, "started": time.time()}
        return f"Playing with {pname} (PID {proc.pid})"
    except Exception as exc:
        logger.debug("YouTube local play failed: %s", exc)
        return None


@tool(
    name="play_url",
    description="Play any media URL — YouTube, direct video/audio files, streaming links.",
    params={
        "url": {"type": "string", "description": "URL to play"},
        "mode": {"type": "string", "description": "'auto' (local first) or 'browser'", "default": "auto", "enum": ["auto", "browser"]},
    },
    required=["url"],
)
def play_url(url: str, mode: str = "auto") -> str:
    import webbrowser
    from urllib.parse import urlparse
    _cleanup_players()
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"Refused non-HTTP URL: {url}"
    if mode == "browser":
        webbrowser.open(url)
        return f"🌐 Opened {url} in browser."

    is_yt = any(d in parsed.netloc for d in ["youtube.com", "youtu.be"])
    if is_yt:
        title = "YouTube Video"
        try:
            from yt_dlp import YoutubeDL
            with YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    title = info.get("title", title)
        except Exception:
            pass
        local = _play_yt_with_player(url, title)
        if local:
            return f"🎬 '{title}'\n   ▶️ {local}"
        webbrowser.open(url)
        return f"🎬 '{title}'\n   🌐 Opened in browser."

    # Non-YouTube URL
    player_bin = _find_player()
    if player_bin:
        try:
            filename = Path(parsed.path).name or "Media"
            if "mpv" in player_bin:
                proc = subprocess.Popen(
                    [player_bin, f"--title={filename}", url],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp,
                )
            else:
                proc = subprocess.Popen(
                    ["nohup", player_bin, "-autoexit", "-window_title", filename[:80], url],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp,
                )
            pname = Path(player_bin).name
            _active_players[pname] = {"pid": proc.pid, "process": proc, "title": filename, "media": url, "started": time.time()}
            return f"▶️ Playing from URL with {pname} (PID {proc.pid}).\n   Use player_control to pause/resume/stop."
        except Exception as exc:
            logger.debug("URL play failed: %s", exc)

    webbrowser.open(url)
    return f"🌐 Opened {url} in browser."


# ---------------------------------------------------------------------------
# Search within a page / URL
# ---------------------------------------------------------------------------


@tool(
    name="search_page",
    description="Fetch any web page URL and search for specific text within its content.",
    params={
        "url": {"type": "string", "description": "URL to fetch and search"},
        "query": {"type": "string", "description": "Text to search for on the page"},
        "max_results": {"type": "integer", "description": "Max matching results (default 20)", "default": 20},
    },
    required=["url", "query"],
)
def search_page(url: str, query: str, max_results: int = 20) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)
    try:
        import requests
        import re
        from html import unescape
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        text = resp.text
        text = unescape(text)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        segments = re.split(r'(?<=[.!?])\s+|\n+', text)
        ql = query.lower()
        matches = [s.strip() for s in segments if ql in s.lower()]
        if not matches:
            return f"No matches for '{query}' on {url}."
        lines = [f"🔍 Found {len(matches)} matches for '{query}' on {parsed.netloc}:\n"]
        for m in matches[:max_results]:
            idx = m.lower().find(ql)
            if idx >= 0:
                before = m[max(0, idx - 40):idx]
                matched = m[idx:idx + len(query)]
                after = m[idx + len(query):idx + len(query) + 40]
                lines.append(f"...{before}[{matched}]{after}...")
            else:
                lines.append(f"  {m[:150]}")
        return "\n".join(lines)
    except requests.Timeout:
        return f"Request timed out fetching {url}"
    except requests.RequestException as e:
        return f"Failed to fetch {url}: {e}"
    except Exception as e:
        return f"Error searching {url}: {e}"
