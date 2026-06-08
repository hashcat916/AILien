"""Media playback tools — local files and YouTube search/play."""

import logging
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
    ".mp3", ".flac", ".wav", ".aac", ".ogg", ".wma", ".m4a", ".opus",      # audio
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",       # video
    ".mpeg", ".mpg", ".3gp", ".ts", ".mts", ".m2ts",
}

# Preferred players in order
PLAYERS = ["celluloid", "vlc", "mpv", "ffplay", "xdg-open"]


def _find_player() -> str | None:
    """Find an available media player."""
    import shutil
    for player in PLAYERS:
        path = shutil.which(player)
        if path:
            return path
    return None


def _search_media(query: str, max_results: int = 20) -> list[Path]:
    """Search for media files matching *query* under *MEDIA_DIRS*."""
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
                # Match against the filename (without extension)
                if query_lower in f.stem.lower():
                    matches.append(f)
        except PermissionError:
            continue

    return matches


@tool(
    name="play_media",
    description="Search for and play a local movie, music file, or video by name.",
    params={
        "query": {
            "type": "string",
            "description": "Name or partial name of the media file to search for (e.g. 'feel good', 'avatar', 'song title')",
        },
        "player": {
            "type": "string",
            "description": "Player to use: 'default' (auto-select), 'celluloid', 'vlc', 'mpv', or 'ffplay'",
            "default": "default",
        },
    },
    required=["query"],
)
def play_media(query: str, player: str = "default") -> str:
    """Search for media files matching *query* and play the best match."""
    if not query.strip():
        return "Please provide a search term."

    matches = _search_media(query)

    if not matches:
        # Try a broader search if nothing found
        for media_dir in MEDIA_DIRS:
            if not media_dir.is_dir():
                continue
            try:
                entries = list(media_dir.iterdir())
                if entries:
                    return (
                        f"No media found matching '{query}'. "
                        f"Files in {media_dir.name}: "
                        + ", ".join(
                            e.stem for e in entries[:20]
                            if e.is_file() and e.suffix.lower() in MEDIA_EXTENSIONS
                        )
                    )
            except PermissionError:
                continue
        return (
            f"No media found matching '{query}'. "
            f"Checked directories: {', '.join(str(d) for d in MEDIA_DIRS if d.is_dir())}."
        )

    # Pick the best match
    target = matches[0]
    if len(matches) > 1:
        # Prefer exact stem match over partial
        exact = [m for m in matches if m.stem.lower() == query.lower()]
        if exact:
            target = exact[0]

    # Determine the player binary
    player_bin: str | None = _find_player()
    if player.lower() != "default":
        import shutil
        player_bin = shutil.which(player)

    if player_bin is None:
        return "No media player found. Install celluloid, vlc, or mpv."

    try:
        if "celluloid" in player_bin:
            # Celluloid opens in GUI mode by default
            subprocess.Popen(
                [player_bin, str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif "ffplay" in player_bin:
            # ffplay is terminal-based — detach with nohup
            subprocess.Popen(
                ["nohup", player_bin, "-nodisp", "-autoexit", str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif "xdg-open" in player_bin:
            subprocess.Popen(
                [player_bin, str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [player_bin, str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        time.sleep(0.5)
        player_name = Path(player_bin).name
        fsize = target.stat().st_size / (1024**2)
        return (
            f"Now playing '{target.stem}' ({fsize:.0f} MB) with {player_name}.\n"
            f"Path: {target}"
        )
    except Exception as e:
        return f"Failed to play media: {e}"


@tool(
    name="list_media",
    description="List available media files in your Music, Videos, Movies, and Downloads folders.",
    params={
        "directory": {
            "type": "string",
            "description": "Directory name to browse: 'music', 'videos', 'downloads', or 'all'",
            "default": "all",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum files to show (default 30)",
            "default": 30,
        },
    },
    required=[],
)
def list_media(directory: str = "all", max_results: int = 30) -> str:
    """List available media files in the user's media directories."""
    dirs_to_check: list[Path] = []

    if directory.lower() in ("music", "audio", "songs"):
        dirs_to_check = [Path.home() / "Music"]
    elif directory.lower() in ("videos", "video", "movies", "movie"):
        dirs_to_check = [Path.home() / "Videos", Path.home() / "Movies"]
    elif directory.lower() in ("downloads", "dl"):
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
                if not f.is_file():
                    continue
                if f.suffix.lower() not in MEDIA_EXTENSIONS:
                    continue
                size = f.stat().st_size / (1024**2)
                kind = "🎵" if f.suffix.lower() in {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".opus"} else "🎬"
                results.append(f"{kind}  {f.stem:40s}  {size:6.0f} MB  ({d.name})")
        except PermissionError:
            continue

    header = f"{'Type':4}  {'Name':40s}  {'Size':>6}  {'Location'}\n{'─'*70}"
    if not results:
        return f"No media files found in {', '.join(str(d) for d in dirs_to_check if d.is_dir())}."

    return header + "\n" + "\n".join(results)


# ---------------------------------------------------------------------------
# YouTube search & playback
# ---------------------------------------------------------------------------


@tool(
    name="youtube_search",
    description="Search YouTube for videos matching a query. Returns titles, channels, durations, and links. Use this before play_youtube to find what you want to watch.",
    params={
        "query": {"type": "string", "description": "What to search for — song name, topic, channel, etc."},
    },
    required=["query"],
)
def youtube_search(query: str) -> str:
    """Search YouTube and return formatted results."""
    try:
        from brain.youtube import search as yt_search
        return yt_search(query)
    except Exception as exc:
        return f"YouTube search failed: {exc}"


def _search_youtube_videos(query: str, max_results: int = 5) -> list[dict]:
    """Get structured video results from YouTube search.

    Returns list of dicts with keys: title, url, video_id, duration, views, channel.
    """
    try:
        from brain.youtube import _extract_with_ytdlp
        videos = _extract_with_ytdlp(f"ytsearch{max_results}:{query}")
        return videos
    except Exception:
        pass

    # Ultra-fallback: direct yt-dlp
    try:
        from yt_dlp import YoutubeDL
        from brain.youtube import _parse_duration as dur, _format_views as vws
        with YoutubeDL({
            "quiet": True, "no_warnings": True,
            "extract_flat": True, "skip_download": True,
            "default_search": "ytsearch",
        }) as ydl:
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


def _play_yt_with_player(video_url: str, title: str) -> str | None:
    """Try to play a YouTube video with a local player.

    Uses yt-dlp to extract the streaming URL, then plays with ffplay.
    Returns None if no player is available.
    """
    try:
        from yt_dlp import YoutubeDL

        # Get the streaming URL
        with YoutubeDL({
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "best[height<=720]/best",  # Cap at 720p for faster start
        }) as ydl:
            info = ydl.extract_info(video_url, download=False)

        # Get the direct media URL
        stream_url = info.get("url")
        if not stream_url:
            return None

        # Try ffplay first
        ffplay = shutil.which("ffplay")
        if ffplay:
            subprocess.Popen(
                ["nohup", ffplay, "-autoexit", "-window_title", title[:50], stream_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return f"ffplay"

        # Try celluloid
        celluloid = shutil.which("celluloid")
        if celluloid:
            subprocess.Popen(
                [celluloid, stream_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return f"celluloid"

    except Exception as exc:
        logger.debug("YouTube play failed: %s", exc)

    return None


@tool(
    name="play_youtube",
    description="Search YouTube for a video and play it. Automatically picks the best match and plays it. If a local player (ffplay) isn't available, it opens in your browser.",
    params={
        "query": {"type": "string", "description": "What to search for and play — song name, video title, topic, etc."},
        "player": {
            "type": "string",
            "description": "How to play: 'auto' (try local player first, then browser), 'browser' (always open in browser)",
            "default": "auto",
            "enum": ["auto", "browser"],
        },
    },
    required=["query"],
)
def play_youtube(query: str, player: str = "auto") -> str:
    """Search YouTube and play the best matching video."""
    import webbrowser

    if not query.strip():
        return "Please provide a search term."

    # Search for videos
    videos = _search_youtube_videos(query)
    if not videos:
        return f"No YouTube results for '{query}'. Try a different search."

    # Pick the best match
    target = videos[0]
    title = target["title"]
    video_url = target["url"]
    channel = target.get("channel", "")
    duration = target.get("duration", "")

    result_parts = [f"🎬 Now playing: {title}"]
    if channel:
        result_parts.append(f"   📺 {channel}")
    if duration:
        result_parts.append(f"   ⏱ {duration}")

    if player == "browser":
        webbrowser.open(video_url)
        result_parts.append(f"   🌐 Opened in browser")
        return "\n".join(result_parts)

    # Try local player first
    player_name = _play_yt_with_player(video_url, title)
    if player_name:
        result_parts.append(f"   ▶️ Playing with {player_name}")
        return "\n".join(result_parts)

    # Fallback: open in browser
    webbrowser.open(video_url)
    result_parts.append(f"   🌐 No local player found — opened in browser")
    result_parts.append(f"   💡 Install mpv for smoother YouTube playback: sudo apt install mpv")
    return "\n".join(result_parts)


@tool(
    name="youtube_trending",
    description="Show currently trending videos on YouTube.",
    params={},
    required=[],
)
def youtube_trending() -> str:
    """Get trending YouTube videos."""
    try:
        from brain.youtube import trending as yt_trending
        return yt_trending()
    except Exception as exc:
        return f"Failed to fetch trending: {exc}"
