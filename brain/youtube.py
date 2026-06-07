"""YouTube quick info — search and get latest videos.

Uses YouTube's public OEmbed API for video info and HTML scraping
for channel feeds and search. No API key required.
"""

import logging
import re
from html import unescape

import requests

logger = logging.getLogger("agent")

_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_TIMEOUT = 15
_MAX_RESULTS = 8


def _fetch(url: str) -> str | None:
    """Fetch a URL and return text, or None on failure."""
    try:
        r = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception as exc:
        logger.debug("YouTube fetch failed: %s", exc)
        return None


def _extract_videos_from_html(html: str) -> list[dict]:
    """Extract video info from YouTube HTML page."""
    videos: list[dict] = []
    # Match video renderer patterns in YouTube HTML
    patterns = [
        # Title
        r'title="([^"]+)"',
        # Video ID in URLs
        r'href="/watch\?v=([a-zA-Z0-9_-]{11})',
        # Channel name
        r'channel-name[^>]*>([^<]+)',
    ]

    # Find all video IDs
    ids = re.findall(patterns[1], html)
    # Find all titles  
    titles = re.findall(patterns[0], html)

    # Match them up
    for i, vid in enumerate(ids[:_MAX_RESULTS]):
        title = unescape(titles[i]) if i < len(titles) else "YouTube Video"
        videos.append({
            "title": title.strip(),
            "url": f"https://youtube.com/watch?v={vid}",
            "video_id": vid,
        })

    return videos


def _extract_search_results(html: str) -> list[dict]:
    """Extract search results from YouTube search page."""
    videos: list[dict] = []

    # Look for video titles and links in the search results
    # YouTube search results contain structured data
    title_pattern = r'<a[^>]*id="video-title"[^>]*title="([^"]+)"'
    link_pattern = r'href="(/watch\?v=[a-zA-Z0-9_-]{11})'

    titles = re.findall(title_pattern, html)[:_MAX_RESULTS]
    links = re.findall(link_pattern, html)

    for i, title in enumerate(titles):
        link = f"https://youtube.com{links[i]}" if i < len(links) else ""
        videos.append({
            "title": unescape(title).strip(),
            "url": link,
        })

    if not videos:
        # Fallback: try broader patterns
        titles = re.findall(r'class="([^"]*title[^"]*)"[^>]*>([^<]+)', html)[:_MAX_RESULTS]
        for cls, title in titles:
            videos.append({
                "title": unescape(title).strip(),
                "url": "",
            })

    return videos


def _format_videos(videos: list[dict], label: str) -> str:
    """Format video list into readable string."""
    if not videos:
        return f"No YouTube results for {label}."

    lines = [f"📺 {label}:"]
    for i, v in enumerate(videos, 1):
        t = v["title"][:100]
        lines.append(f"{i}. {t}")
    return "\n".join(lines)


def search(query: str) -> str:
    """Search YouTube for videos."""
    html = _fetch(f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}")
    if not html:
        return f"Could not search YouTube for '{query}'."
    videos = _extract_search_results(html)
    return _format_videos(videos, f"'{query}'")


def trending() -> str:
    """Get trending YouTube videos."""
    html = _fetch("https://www.youtube.com/feed/trending")
    if not html:
        return "Could not fetch YouTube trending."
    videos = _extract_videos_from_html(html)
    return _format_videos(videos, "Trending")


def channel_videos(channel_name: str) -> str:
    """Get latest videos from a channel."""
    # Try direct channel URL
    html = _fetch(f"https://www.youtube.com/@{channel_name}/videos")
    if not html:
        html = _fetch(f"https://www.youtube.com/c/{channel_name}/videos")
    if not html:
        html = _fetch(f"https://www.youtube.com/{channel_name}/videos")
    if not html:
        return f"Could not find channel '{channel_name}'."
    videos = _extract_videos_from_html(html)
    return _format_videos(videos, f"Latest from @{channel_name}")
