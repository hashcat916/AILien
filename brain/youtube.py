"""YouTube quick info — search, trending, and channel videos.

Uses yt-dlp for reliable metadata extraction (no API key required)
with BeautifulSoup HTML parsing as a fallback for search results.
"""

import logging
import re
from html import unescape
from typing import Any

import requests

logger = logging.getLogger("agent")

_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_TIMEOUT = 15
_MAX_RESULTS = 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch(url: str) -> str | None:
    """Fetch a URL and return text, or None on failure."""
    try:
        r = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.text
    except requests.RequestException as exc:
        logger.debug("YouTube fetch failed: %s", exc)
        return None


def _format_videos(videos: list[dict], label: str) -> str:
    """Format video list into readable string."""
    if not videos:
        return f"No YouTube results for {label}."

    lines = [f"📺 {label}:"]
    for i, v in enumerate(videos, 1):
        title = v.get("title", "Untitled")[:100]
        url = v.get("url", "")
        duration = v.get("duration", "")
        views = v.get("views", "")
        channel = v.get("channel", "")
        uploaded = v.get("uploaded", "")

        parts = [f"{i}. {title}"]
        meta = []
        if channel:
            meta.append(f"📺 {channel}")
        if duration:
            meta.append(f"⏱ {duration}")
        if views:
            meta.append(f"👁 {views}")
        if uploaded:
            meta.append(f"📅 {uploaded}")
        if meta:
            parts.append(f"   {' · '.join(meta)}")
        if url:
            parts.append(f"   🔗 {url}")
        lines.append("\n".join(parts))
    return "\n".join(lines)


def _parse_duration(seconds: int | None) -> str:
    """Convert seconds to HH:MM:SS or MM:SS format."""
    if not seconds:
        return ""
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_views(count: int | None) -> str:
    """Format view count (e.g. 1.2M, 500K)."""
    if not count:
        return ""
    count = int(count)
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


# ---------------------------------------------------------------------------
# yt-dlp based extraction (primary)
# ---------------------------------------------------------------------------


def _extract_with_ytdlp(url: str) -> list[dict]:
    """Extract video entries using yt-dlp (no download).

    Returns a list of video dicts with keys: title, url, duration, views,
    channel, uploaded.
    """
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        logger.debug("yt-dlp not available")
        return []

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
    }

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        logger.debug("yt-dlp extraction failed for %s: %s", url, exc)
        return []

    entries: list[dict] = info.get("entries", []) if info else []
    results = []
    for entry in entries[: _MAX_RESULTS + 2]:  # extra for filtering
        if not entry or not entry.get("id"):
            continue
        results.append({
            "title": entry.get("title", "Unknown"),
            "url": f"https://youtube.com/watch?v={entry['id']}",
            "video_id": entry["id"],
            "duration": _parse_duration(entry.get("duration")),
            "views": _format_views(entry.get("view_count")),
            "channel": entry.get("channel", entry.get("uploader", "")),
            "uploaded": entry.get("upload_date", "")[:10] if entry.get("upload_date") else "",
        })
        if len(results) >= _MAX_RESULTS:
            break
    return results


# ---------------------------------------------------------------------------
# HTML / regex fallback (when yt-dlp is unavailable)
# ---------------------------------------------------------------------------


def _extract_videos_from_html(html: str) -> list[dict]:
    """Extract video info from YouTube HTML using BeautifulSoup.

    Falls back to regex if BeautifulSoup is not available.
    """
    try:
        return _extract_with_bs4(html)
    except ImportError:
        return _extract_with_regex(html)


def _extract_with_bs4(html: str) -> list[dict]:
    """Extract video info from YouTube HTML using BeautifulSoup."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    videos: list[dict] = []
    seen_ids: set[str] = set()

    # Try to find video data in ytInitialData JSON
    import json
    script = soup.find("script", string=re.compile(r"ytInitialData"))
    if script:
        try:
            match = re.search(r"ytInitialData\s*=\s*({.*?});", script.string, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                # Navigate the complex YouTube response structure
                contents = (
                    data.get("contents", {})
                    .get("twoColumnSearchResultsRenderer", {})
                    .get("primaryContents", {})
                    .get("sectionListRenderer", {})
                    .get("contents", [])
                )
                for section in contents:
                    items = (
                        section.get("itemSectionRenderer", {})
                        .get("contents", [])
                    )
                    for item in items:
                        vr = item.get("videoRenderer", {})
                        if not vr:
                            continue
                        vid = vr.get("videoId", "")
                        if vid in seen_ids:
                            continue
                        seen_ids.add(vid)
                        title_runs = (
                            vr.get("title", {})
                            .get("runs", [])
                        )
                        title = "".join(
                            r.get("text", "") for r in title_runs
                        ) or vr.get("title", {}).get("simpleText", "Unknown")

                        # Duration
                        duration = ""
                        dur_simple = (
                            vr.get("lengthText", {})
                            .get("simpleText", "")
                        )
                        if dur_simple:
                            duration = dur_simple

                        # Views
                        views = ""
                        view_text = (
                            vr.get("viewCountText", {})
                            .get("simpleText", "")
                            or (
                                vr.get("viewCountText", {})
                                .get("runs", [{}])[0]
                                .get("text", "")
                            )
                        )
                        if view_text:
                            views = view_text.replace("views", "").strip()

                        # Channel
                        channel = ""
                        owner = (
                            vr.get("ownerText", {})
                            .get("runs", [{}])[0]
                            .get("text", "")
                        )
                        if owner:
                            channel = owner

                        videos.append({
                            "title": unescape(title).strip(),
                            "url": f"https://youtube.com/watch?v={vid}",
                            "video_id": vid,
                            "duration": duration,
                            "views": views,
                            "channel": channel,
                            "uploaded": "",
                        })
                        if len(videos) >= _MAX_RESULTS:
                            break
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.debug("Failed to parse ytInitialData: %s", exc)

    return videos


def _extract_with_regex(html: str) -> list[dict]:
    """Fallback: extract video info from YouTube HTML using regex."""
    videos: list[dict] = []
    ids = re.findall(r'href="/watch\?v=([a-zA-Z0-9_-]{11})', html)
    titles = re.findall(r'title="([^"]+)"', html)

    for i, vid in enumerate(ids[:_MAX_RESULTS]):
        title = unescape(titles[i]) if i < len(titles) else "YouTube Video"
        videos.append({
            "title": title.strip(),
            "url": f"https://youtube.com/watch?v={vid}",
            "video_id": vid,
            "duration": "",
            "views": "",
            "channel": "",
            "uploaded": "",
        })
    return videos


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def search(query: str) -> str:
    """Search YouTube for videos."""
    # 1. Try yt-dlp (most reliable)
    try:
        videos = _extract_with_ytdlp(f"ytsearch{_MAX_RESULTS}:{query}")
        if videos:
            return _format_videos(videos, f"'{query}'")
    except Exception as exc:
        logger.debug("yt-dlp search failed: %s", exc)

    # 2. Try HTML scraping
    html = _fetch(
        f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}"
    )
    if html:
        videos = _extract_videos_from_html(html)
        if videos:
            return _format_videos(videos, f"'{query}'")

    return f"Could not search YouTube for '{query}'. Try a different query."


def trending() -> str:
    """Get trending YouTube videos."""
    # 1. Try yt-dlp
    try:
        videos = _extract_with_ytdlp("https://www.youtube.com/feed/trending")
        if videos:
            return _format_videos(videos, "Trending")
    except Exception as exc:
        logger.debug("yt-dlp trending failed: %s", exc)

    # 2. Try HTML scraping
    html = _fetch("https://www.youtube.com/feed/trending")
    if html:
        videos = _extract_videos_from_html(html)
        if videos:
            return _format_videos(videos, "Trending")

    return "Could not fetch YouTube trending."


def channel_videos(channel_name: str) -> str:
    """Get latest videos from a channel."""
    urls_to_try = [
        f"https://www.youtube.com/@{channel_name}/videos",
        f"https://www.youtube.com/c/{channel_name}/videos",
        f"https://www.youtube.com/{channel_name}/videos",
    ]

    # 1. Try yt-dlp on each URL
    for url in urls_to_try:
        try:
            videos = _extract_with_ytdlp(url)
            if videos:
                return _format_videos(videos, f"Latest from @{channel_name}")
        except Exception as exc:
            logger.debug("yt-dlp channel fetch failed for %s: %s", url, exc)

    # 2. Try HTML scraping
    for url in urls_to_try:
        html = _fetch(url)
        if html:
            videos = _extract_videos_from_html(html)
            if videos:
                return _format_videos(videos, f"Latest from @{channel_name}")

    return f"Could not find channel '{channel_name}'."


def video_info(video_id: str) -> str:
    """Get detailed info about a single video using oEmbed API.

    Works without any API key — YouTube's oEmbed is a public endpoint.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    oembed_url = f"https://www.youtube.com/oembed?url={requests.utils.quote(url)}&format=json"

    try:
        r = requests.get(oembed_url, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        lines = [
            f"🎬 {data.get('title', 'Unknown')}",
            f"   📺 Channel: {data.get('author_name', 'Unknown')}",
            f"   🔗 {url}",
        ]
        return "\n".join(lines)
    except requests.RequestException as exc:
        # Fallback to yt-dlp
        try:
            from yt_dlp import YoutubeDL
            with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            if info:
                lines = [
                    f"🎬 {info.get('title', 'Unknown')}",
                    f"   📺 Channel: {info.get('channel', info.get('uploader', 'Unknown'))}",
                    f"   ⏱ {_parse_duration(info.get('duration'))}",
                    f"   👁 {_format_views(info.get('view_count'))}",
                    f"   🔗 {url}",
                ]
                return "\n".join(lines)
        except Exception:
            pass
        return f"Could not fetch video info: {exc}"
