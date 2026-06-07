"""Note-taking tools — save voice/text notes, list notes, read/search notes."""
from datetime import datetime
from pathlib import Path
import config

from tools import tool


def _notes_dir() -> Path:
    """Get or create the notes directory inside knowledge."""
    notes_dir = config.PROJECT_DIR / "knowledge" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    return notes_dir


def _safe_filename(title: str) -> str:
    """Convert a title to a safe filename."""
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    return safe.strip()[:80] or "note"


@tool(
    name="take_note",
    description="Save a note to the local knowledge base. Use this to remember anything the user says or to take voice/text notes.",
    params={
        "title": {"type": "string", "description": "A short title for the note (e.g. 'Grocery list', 'Idea for app')"},
        "content": {"type": "string", "description": "The content of the note"},
    },
    required=["title", "content"],
)
def take_note(title: str, content: str) -> str:
    notes_dir = _notes_dir()
    filename = _safe_filename(title) + ".md"
    filepath = notes_dir / filename

    # Append date
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    note_content = f"# {title}\n\n_{date_str}_\n\n{content}\n"

    try:
        filepath.write_text(note_content, encoding="utf-8")
        return f"Note saved: {title} → knowledge/notes/{filename}"
    except Exception as e:
        return f"Failed to save note: {e}"


@tool(
    name="list_notes",
    description="List all saved notes in the knowledge base.",
    params={},
    required=[],
)
def list_notes() -> str:
    notes_dir = _notes_dir()
    files = sorted(notes_dir.glob("*.md"))
    if not files:
        return "No notes saved yet. Use 'take_note' to save one."

    lines = []
    for f in files:
        # Read just the first line (title)
        try:
            first_line = f.read_text(encoding="utf-8").split("\n")[0].strip("# ")
            lines.append(f"  {f.stem} — {first_line[:60]}")
        except Exception:
            lines.append(f"  {f.stem}")
    return "Saved notes:\n" + "\n".join(lines)


@tool(
    name="read_note",
    description="Read the full content of a saved note by its title or filename.",
    params={
        "title": {"type": "string", "description": "The title or filename of the note to read (partial match OK)"},
    },
    required=["title"],
)
def read_note(title: str) -> str:
    notes_dir = _notes_dir()
    title_lower = title.lower().strip()

    # Try exact match first, then partial match
    for f in sorted(notes_dir.glob("*.md")):
        if title_lower == f.stem.lower() or title_lower in f.stem.lower():
            try:
                content = f.read_text(encoding="utf-8")
                return content
            except Exception as e:
                return f"Could not read note '{f.stem}': {e}"

    return f"Note '{title}' not found. Use 'list_notes' to see available notes."


@tool(
    name="search_notes",
    description="Search the content of all saved notes for a keyword or phrase.",
    params={
        "query": {"type": "string", "description": "The keyword or phrase to search for"},
    },
    required=["query"],
)
def search_notes(query: str) -> str:
    notes_dir = _notes_dir()
    query_lower = query.lower()
    results = []

    for f in sorted(notes_dir.glob("*.md")):
        try:
            content = f.read_text(encoding="utf-8")
            if query_lower in content.lower():
                # Find the matching line
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if query_lower in line.lower():
                        preview = line.strip()[:100]
                        results.append(f"  {f.stem} (line {i+1}): {preview}")
                        break
        except Exception:
            continue

    if not results:
        return f"No notes found matching '{query}'."
    return f"Notes matching '{query}':\n" + "\n".join(results[:10])


@tool(
    name="delete_note",
    description="Delete a saved note by its title or filename.",
    params={
        "title": {"type": "string", "description": "The title or filename of the note to delete"},
    },
    required=["title"],
)
def delete_note(title: str) -> str:
    notes_dir = _notes_dir()
    title_lower = title.lower().strip()

    for f in list(notes_dir.glob("*.md")):
        if title_lower == f.stem.lower() or title_lower in f.stem.lower():
            try:
                f.unlink()
                return f"Deleted note: {f.stem}"
            except Exception as e:
                return f"Could not delete note '{f.stem}': {e}"

    return f"Note '{title}' not found."
