"""Knowledge base — local directory of useful info that AILIEN can search, read, and save to.

Knowledge files live in ``PROJECT_DIR/knowledge/`` and are markdown (.md) or
plain text (.txt). The system can:

- Search for files by topic
- Read file contents
- Save new information (via 'save that' command)
- List available topics
"""

import logging
import re
from pathlib import Path
from typing import Iterator

import config

logger = logging.getLogger("agent")

KNOWLEDGE_DIR = config.PROJECT_DIR / "knowledge"


def _ensure_dir() -> None:
    """Create the knowledge directory if it doesn't exist."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    (KNOWLEDGE_DIR / "cheatsheets").mkdir(exist_ok=True)
    (KNOWLEDGE_DIR / "notes").mkdir(exist_ok=True)
    (KNOWLEDGE_DIR / "topics").mkdir(exist_ok=True)


def list_topics() -> str:
    """List all knowledge files organized by directory."""
    _ensure_dir()
    sections: list[str] = []

    for subdir in sorted(KNOWLEDGE_DIR.iterdir()):
        if not subdir.is_dir():
            continue
        files = sorted(subdir.glob("*.md")) + sorted(subdir.glob("*.txt"))
        if not files:
            continue
        title = subdir.name.replace("_", " ").replace("-", " ").title()
        entries = [f"  • {f.stem.replace('_', ' ').replace('-', ' ').title()}" for f in files]
        sections.append(f"[{title}]\n" + "\n".join(entries))

    if not sections:
        return "Knowledge base is empty. Say 'save that' to add something."

    return "Available knowledge:\n" + "\n\n".join(sections)


def search(query: str) -> str:
    """Search knowledge files for a query. Returns matching snippets."""
    _ensure_dir()
    query_lower = query.lower()
    results: list[tuple[Path, str, int]] = []  # (file, line, line_no)

    for f in _walk_files():
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines, 1):
                if query_lower in line.lower():
                    results.append((f, line.strip(), i))
        except Exception:
            continue

    if not results:
        return f"No results found for '{query}' in the knowledge base."

    # Group by file
    by_file: dict[str, list[str]] = {}
    for f, line, lineno in results[:20]:
        relative = f.relative_to(KNOWLEDGE_DIR)
        key = str(relative)
        if key not in by_file:
            by_file[key] = []
        by_file[key].append(f"  L{lineno}: {line[:120]}")

    parts = [f"Found {len(results)} result(s) for '{query}':"]
    for filepath, matches in by_file.items():
        parts.append(f"\n📄 {filepath}:")
        parts.extend(matches)

    return "\n".join(parts)


def read(topic: str) -> str:
    """Read a knowledge file by name (partial match)."""
    _ensure_dir()
    topic_lower = topic.lower()

    best: Path | None = None
    for f in _walk_files():
        if topic_lower in f.stem.lower():
            best = f
            break

    if best is None:
        # Try matching content
        results = search(topic)
        if "No results" not in results:
            return results
        return f"No knowledge file found matching '{topic}'. Say 'list knowledge' to see what's available."

    content = best.read_text(encoding="utf-8")
    return f"📄 {best.relative_to(KNOWLEDGE_DIR)}\n{'-'*40}\n{content}"


def save(title: str, content: str, category: str = "notes") -> str:
    """Save a new knowledge entry.

    Args:
        title: File name (without extension)
        content: File content (markdown recommended)
        category: Subdirectory (notes, cheatsheets, topics)
    """
    _ensure_dir()
    # Sanitize the title to a safe filename
    safe_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', title).strip().replace(' ', '_')
    if not safe_title:
        safe_title = "note"

    cat_dir = KNOWLEDGE_DIR / category
    cat_dir.mkdir(exist_ok=True)

    filepath = cat_dir / f"{safe_title}.md"

    # Format as markdown
    formatted = f"# {title}\n\n_{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n{content}\n"

    try:
        filepath.write_text(formatted, encoding="utf-8")
        logger.info("Saved knowledge: %s", filepath)
        return f"Saved to knowledge base: {filepath.relative_to(KNOWLEDGE_DIR)}"
    except Exception as exc:
        return f"Failed to save knowledge: {exc}"


def _walk_files() -> Iterator[Path]:
    """Walk all knowledge files."""
    _ensure_dir()
    for ext in ("*.md", "*.txt"):
        yield from KNOWLEDGE_DIR.rglob(ext)
