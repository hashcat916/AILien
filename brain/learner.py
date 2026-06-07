"""Learner — AILIEN can research topics from the web and save what it learns.

The learner fetches information from web sources (articles, documentation, 
Reddit, YouTube, etc.), extracts the relevant content, and saves it 
to the knowledge base for future reference.

This makes AILIEN smarter over time — it remembers what it learned.
"""

import json
import logging
import re
import time
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

logger = logging.getLogger("agent")

# Knowledge categories for learned information
LEARNING_CATEGORIES = {
    "programming": "Programming languages, frameworks, tools, best practices",
    "computer_science": "CS concepts: algorithms, data structures, theory",
    "linux": "Linux commands, system administration, shell scripting",
    "web": "Web development, HTML/CSS/JS, APIs, protocols",
    "python": "Python-specific: libraries, patterns, tips",
    "general": "General knowledge and miscellaneous topics",
}

# Cache directory for learned content metadata
_LEARNER_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "learner"
_LEARNER_INDEX_FILE = _LEARNER_CACHE_DIR / "learned_index.json"

_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AILIEN-Learner/1.0"


def _ensure_cache() -> None:
    """Create the learner cache directory."""
    _LEARNER_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> dict[str, Any]:
    """Load the learning index (what has been learned)."""
    _ensure_cache()
    if _LEARNER_INDEX_FILE.exists():
        try:
            return json.loads(_LEARNER_INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"entries": [], "topics": {}}


def _save_index(index: dict[str, Any]) -> None:
    """Save the learning index."""
    _ensure_cache()
    _LEARNER_INDEX_FILE.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _fetch_url(url: str, timeout: int = 15) -> str | None:
    """Fetch a URL and return its text content, or None on failure."""
    try:
        import requests
        r = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.text
    except ImportError:
        logger.warning("requests not available, cannot fetch URLs")
        return None
    except Exception as exc:
        logger.debug("Fetch failed for %s: %s", url, exc)
        return None


def _extract_text_from_html(html: str, max_chars: int = 8000) -> str:
    """Extract readable text from HTML content.

    Strips scripts, styles, and tags. Returns clean text.
    """
    # Remove scripts and styles
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Replace <br> and block-level tags with newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|h[1-6]|li|tr|blockquote|pre)>', '\n', text, flags=re.IGNORECASE)

    # Strip all remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # Decode HTML entities
    text = unescape(text)

    # Collapse whitespace
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(line for line in lines if line)

    return text[:max_chars]


def _categorize_topic(topic: str) -> str:
    """Auto-categorize a topic based on keywords."""
    topic_lower = topic.lower()

    # Check programming languages
    lang_keywords = {
        "python": "python",
        "javascript": "programming", "java": "programming",
        "rust": "programming", "go ": "programming", "golang": "programming",
        "typescript": "programming", "c++": "programming", "c#": "programming",
        "ruby": "programming", "php": "programming",
    }
    for kw, cat in lang_keywords.items():
        if kw in topic_lower:
            return cat

    # Check CS concepts
    cs_keywords = [
        "algorithm", "data structure", "big o", "complexity",
        "recursion", "sorting", "search", "graph", "tree",
        "binary", "hash", "stack", "queue", "linked list",
        "dynamic programming", "machine learning", "ai",
    ]
    for kw in cs_keywords:
        if kw in topic_lower:
            return "computer_science"

    # Check Linux
    linux_keywords = ["linux", "bash", "shell", "command", "terminal", "ubuntu",
                      "debian", "cron", "systemd", "permission"]
    for kw in linux_keywords:
        if kw in topic_lower:
            return "linux"

    # Check web
    web_keywords = ["html", "css", "react", "vue", "angular", "api", "rest",
                    "http", "web", "node", "npm", "django", "flask", "fastapi"]
    for kw in web_keywords:
        if kw in topic_lower:
            return "web"

    return "general"


def _get_title_from_html(html: str) -> str:
    """Extract the <title> from HTML."""
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if m:
        return unescape(m.group(1).strip())
    return ""


def learn_from_url(url: str, topic: str | None = None, max_chars: int = 8000) -> str:
    """Learn from a URL: fetch, extract, save to knowledge base.

    Args:
        url: The URL to learn from
        topic: Optional topic name (auto-detected from content if not provided)
        max_chars: Maximum characters to extract

    Returns:
        A message describing what was learned
    """
    # Fetch the URL
    html = _fetch_url(url)
    if html is None:
        return f"Could not fetch {url}. Check the URL and try again."

    # Extract title
    page_title = _get_title_from_html(html)
    if not page_title:
        page_title = topic or "Web Research"

    # Extract readable text
    text = _extract_text_from_html(html, max_chars=max_chars)
    if not text.strip():
        return f"Could not extract readable content from {url}."

    # Determine topic name
    topic_name = topic or page_title[:50]

    # Auto-categorize
    category = _categorize_topic(topic_name)

    # Save to knowledge base
    try:
        from brain.knowledge import save as kb_save
        source_line = f"\n\n_Source: [{url}]({url})_\n_Learned: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n---\n\n"
        content = source_line + text
        result = kb_save(topic_name, content, category="topics")
    except Exception as exc:
        result = f"Saved to cache (knowledge base unavailable: {exc})"

    # Add to learning index
    index = _load_index()
    entry = {
        "topic": topic_name,
        "url": url,
        "page_title": page_title,
        "category": category,
        "learned_at": datetime.now().isoformat(),
        "char_count": len(text),
    }
    index["entries"].append(entry)
    index["topics"][topic_name.lower()] = {
        "category": category,
        "sources": index["topics"].get(topic_name.lower(), {}).get("sources", []) + [url],
        "learned_at": datetime.now().isoformat(),
    }
    _save_index(index)

    # Summary
    char_preview = text[:200].replace("\n", " ").strip()
    return (
        f"✅ Learned about: **{topic_name}**\n"
        f"   Category: {category}\n"
        f"   Source: {page_title}\n"
        f"   Content: {len(text)} characters saved\n"
        f"   Preview: {char_preview}...\n"
        f"   {result}"
    )


def learn_from_reddit(subreddit: str, query: str | None = None, limit: int = 5) -> str:
    """Learn from Reddit — fetches posts and saves them to the knowledge base."""
    try:
        from brain.reddit import hot, search as reddit_search
    except ImportError:
        return "Reddit module not available."

    if query:
        posts_text = reddit_search(query, subreddit)
        topic = f"Reddit: {query} (r/{subreddit})"
    else:
        posts_text = hot(subreddit)
        topic = f"Reddit Hot: r/{subreddit}"

    # Save to knowledge base
    try:
        from brain.knowledge import save as kb_save
        content = f"Source: Reddit r/{subreddit}\nLearned: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{posts_text}"
        kb_save(topic, content, category="topics")
    except Exception as exc:
        return f"Retrieved but couldn't save: {exc}"

    return f"✅ Learned from Reddit: {topic}\n{posts_text}"


def learn_from_youtube(query: str, limit: int = 5) -> str:
    """Learn from YouTube — searches for videos and saves results."""
    try:
        from brain.youtube import search as yt_search
    except ImportError:
        return "YouTube module not available."

    videos_text = yt_search(query)
    topic = f"YouTube: {query}"

    # Save to knowledge base
    try:
        from brain.knowledge import save as kb_save
        content = f"Source: YouTube search for '{query}'\nLearned: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{videos_text}"
        kb_save(topic, content, category="topics")
    except Exception as exc:
        return f"Retrieved but couldn't save: {exc}"

    return f"✅ Learned from YouTube: {topic}\n{videos_text}"


def recall(topic: str) -> str:
    """Recall what AILIEN knows about a topic from the knowledge base and learning index.

    Searches both the knowledge base files and the learning index.
    """
    results = []

    # Search knowledge base
    try:
        from brain.knowledge import search as kb_search, read as kb_read
        kb_result = kb_search(topic)
        if "No results found" not in kb_result:
            results.append(kb_result)
    except Exception:
        pass

    # Search learning index
    index = _load_index()
    topic_lower = topic.lower()
    learned_about = []

    for entry in index.get("entries", []):
        if topic_lower in entry.get("topic", "").lower():
            learned_about.append(entry)
        elif topic_lower in entry.get("category", "").lower():
            learned_about.append(entry)

    if learned_about:
        lines = [f"\n📚 Previously learned about '{topic}':"]
        for entry in learned_about[-5:]:  # Last 5
            lines.append(
                f"  • {entry['topic']}  ({entry['category']})  "
                f"— from {entry.get('page_title', entry['url'])} "
                f"on {entry['learned_at'][:10]}"
            )
        results.append("\n".join(lines))

    if not results:
        return f"I don't know much about '{topic}' yet. Try 'learn_from_web about {topic}' to research it."

    return "\n".join(results)


def list_learned_topics() -> str:
    """List all topics that have been learned."""
    index = _load_index()
    entries = index.get("entries", [])

    if not entries:
        return "I haven't learned anything yet. Try 'learn from web about <topic>' to get started."

    # Group by category
    by_category: dict[str, list[dict]] = {}
    for entry in entries:
        cat = entry.get("category", "general")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(entry)

    lines = ["📖 What I've learned so far:"]
    for cat in sorted(by_category.keys()):
        cat_label = LEARNING_CATEGORIES.get(cat, cat.title())
        lines.append(f"\n  [{cat_label}]")
        for entry in by_category[cat][-8:]:  # Last 8 per category
            lines.append(f"    • {entry['topic']}  ({entry['learned_at'][:10]})")

    lines.append(f"\nTotal: {len(entries)} learning session(s)")
    return "\n".join(lines)


def forget_topic(topic: str) -> str:
    """Remove a learned topic from the index (knowledge base file stays)."""
    index = _load_index()
    topic_lower = topic.lower()

    # Remove from entries
    before_count = len(index.get("entries", []))
    index["entries"] = [
        e for e in index.get("entries", [])
        if topic_lower not in e.get("topic", "").lower()
    ]
    after_count = len(index["entries"])

    # Remove from topics
    if topic_lower in index.get("topics", {}):
        del index["topics"][topic_lower]

    _save_index(index)

    removed = before_count - after_count
    if removed > 0:
        return f"Forgot {removed} entry/entries related to '{topic}'."
    return f"No learned entries found for '{topic}'."
