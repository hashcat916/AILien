"""Reddit quick info — fetch hot posts, subreddit top, and search.

Uses Reddit's Atom RSS feeds which are freely accessible without authentication.
Fallback to HTML scraping if RSS is unavailable.
"""

import logging
import re
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger("agent")

_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AILIEN/1.0"
_TIMEOUT = 15
_MAX_RESULTS = 8


def _fetch_rss(url: str) -> str | None:
    """Fetch an RSS/Atom feed and return the XML text, or None on failure."""
    try:
        r = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.text
    except Exception as exc:
        logger.debug("Reddit RSS fetch failed: %s", exc)
        return None


def _parse_atom(xml_text: str) -> list[dict]:
    """Parse an Atom feed into a list of {title, link, summary} dicts."""
    results: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns)[:_MAX_RESULTS]:
            title = entry.findtext("atom:title", "", ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            summary = entry.findtext("atom:content", "", ns) or entry.findtext("atom:summary", "", ns)
            # Clean up summary — strip HTML tags
            summary = re.sub(r"<[^>]+>", "", summary)[:200] if summary else ""
            results.append({"title": title.strip(), "link": link, "summary": summary.strip()})
    except Exception as exc:
        logger.debug("Atom parse failed: %s", exc)
    return results


def _format_posts(posts: list[dict], title: str) -> str:
    """Format a list of Reddit posts into a readable string."""
    if not posts:
        return f"No Reddit posts found for {title}."

    lines = [f"🔥 {title}:"]
    for i, post in enumerate(posts, 1):
        t = post["title"][:120]
        lines.append(f"{i}. {t}")
    return "\n".join(lines)


def hot(subreddit: str = "all") -> str:
    """Get hot posts from a subreddit."""
    sub = subreddit.strip("r/").lower()
    url = f"https://www.reddit.com/r/{sub}/hot/.rss"
    xml = _fetch_rss(url)
    if not xml:
        return f"Could not fetch Reddit r/{sub}. Reddit may be rate-limiting us."
    posts = _parse_atom(xml)
    label = f"Hot on r/{sub}"
    return _format_posts(posts, label)


def top(subreddit: str = "all", time_filter: str = "day") -> str:
    """Get top posts from a subreddit for a time period."""
    sub = subreddit.strip("r/").lower()
    url = f"https://www.reddit.com/r/{sub}/top/.rss?t={time_filter}"
    xml = _fetch_rss(url)
    if not xml:
        return f"Could not fetch Reddit r/{sub}. Reddit may be rate-limiting us."
    posts = _parse_atom(xml)
    label = f"Top on r/{sub} ({time_filter})"
    return _format_posts(posts, label)


def search(query: str, subreddit: str = "all") -> str:
    """Search Reddit for a query."""
    sub = subreddit.strip("r/").lower()
    url = f"https://www.reddit.com/r/{sub}/search/.rss?q={requests.utils.quote(query)}&sort=relevance&t=week"
    xml = _fetch_rss(url)
    if not xml:
        return f"Could not search Reddit for '{query}'."
    posts = _parse_atom(xml)
    label = f"r/{sub}: '{query}'"
    return _format_posts(posts, label)
