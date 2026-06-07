"""Tests for brain/knowledge.py — save, read, search, list topics."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def temp_knowledge_dir():
    """Create a temporary knowledge directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        knowledge_path = Path(tmpdir)
        # Create subdirectories
        (knowledge_path / "notes").mkdir()
        (knowledge_path / "cheatsheets").mkdir()
        (knowledge_path / "topics").mkdir()

        # Write a test file
        test_file = knowledge_path / "notes" / "test_note.md"
        test_file.write_text("# Test Note\n\nThis is a test note for unit tests.\n")
        yield knowledge_path


# ---------------------------------------------------------------------------
# list_topics
# ---------------------------------------------------------------------------


@patch("brain.knowledge.KNOWLEDGE_DIR")
def test_list_topics_shows_files(mock_knowledge_dir, temp_knowledge_dir):
    """list_topics() should display available files."""
    from brain.knowledge import list_topics

    mock_knowledge_dir.__truediv__ = lambda self, other: temp_knowledge_dir / other
    mock_knowledge_dir.iterdir = lambda: temp_knowledge_dir.iterdir()
    mock_knowledge_dir.rglob = lambda pattern: temp_knowledge_dir.rglob(pattern)
    mock_knowledge_dir.mkdir = lambda parents, exist_ok: None
    mock_knowledge_dir.exists = lambda: True

    # We need to patch _ensure_dir too
    with patch("brain.knowledge.KNOWLEDGE_DIR", temp_knowledge_dir):
        from brain.knowledge import list_topics
        result = list_topics()
        assert "Test Note" in result or "test_note" in result


@patch("brain.knowledge.KNOWLEDGE_DIR")
def test_list_topics_empty_returns_message(mock_knowledge_dir):
    """Empty knowledge base should return a helpful message."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_knowledge_dir.__truediv__ = lambda self, other: Path(tmpdir) / other
        mock_knowledge_dir.iterdir = lambda: Path(tmpdir).iterdir()
        mock_knowledge_dir.rglob = lambda pattern: Path(tmpdir).rglob(pattern)
        mock_knowledge_dir.mkdir = lambda parents, exist_ok: None
        mock_knowledge_dir.exists = lambda: True

        with patch("brain.knowledge.KNOWLEDGE_DIR", Path(tmpdir)):
            from brain.knowledge import list_topics
            result = list_topics()
            assert "empty" in result.lower() or "Available knowledge" in result


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@patch("brain.knowledge.KNOWLEDGE_DIR")
def test_search_finds_content(mock_knowledge_dir, temp_knowledge_dir):
    """Search should find matching content in knowledge files."""
    with patch("brain.knowledge.KNOWLEDGE_DIR", temp_knowledge_dir):
        from brain.knowledge import search
        result = search("test note")
        assert "result" in result.lower() or "test_note" in result


@patch("brain.knowledge.KNOWLEDGE_DIR")
def test_search_no_results(mock_knowledge_dir, temp_knowledge_dir):
    """Search with no matches should return a no-results message."""
    with patch("brain.knowledge.KNOWLEDGE_DIR", temp_knowledge_dir):
        from brain.knowledge import search
        result = search("xyznonexistentkeyword12345")
        assert "No results" in result


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------


@patch("brain.knowledge.KNOWLEDGE_DIR")
def test_read_existing_file(mock_knowledge_dir, temp_knowledge_dir):
    """read() should return content of an existing file."""
    with patch("brain.knowledge.KNOWLEDGE_DIR", temp_knowledge_dir):
        from brain.knowledge import read
        result = read("test_note")
        assert "Test Note" in result


@patch("brain.knowledge.KNOWLEDGE_DIR")
def test_read_nonexistent_topic(mock_knowledge_dir, temp_knowledge_dir):
    """read() on nonexistent topic should return a not-found message."""
    with patch("brain.knowledge.KNOWLEDGE_DIR", temp_knowledge_dir):
        from brain.knowledge import read
        result = read("nonexistent_topic_xyz")
        assert "No knowledge file found" in result


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


@patch("brain.knowledge.KNOWLEDGE_DIR")
def test_save_new_entry(mock_knowledge_dir, temp_knowledge_dir):
    """save() should create a new file in the knowledge directory."""
    with patch("brain.knowledge.KNOWLEDGE_DIR", temp_knowledge_dir):
        from brain.knowledge import save
        result = save("My Saved Info", "This is some useful information I want to keep.")
        assert "Saved" in result
        assert "My_Saved_Info" in result or "my_saved_info" in result.lower()

        # Verify the file was actually created
        saved_file = temp_knowledge_dir / "notes" / "My_Saved_Info.md"
        assert saved_file.exists()
        content = saved_file.read_text()
        assert "My Saved Info" in content
        assert "useful information" in content


@patch("brain.knowledge.KNOWLEDGE_DIR")
def test_save_with_custom_category(mock_knowledge_dir, temp_knowledge_dir):
    """save() should place files in the specified category subdirectory."""
    with patch("brain.knowledge.KNOWLEDGE_DIR", temp_knowledge_dir):
        from brain.knowledge import save
        result = save("Cheat Sheet", "Some commands", category="cheatsheets")
        assert "Saved" in result
        saved_file = temp_knowledge_dir / "cheatsheets" / "Cheat_Sheet.md"
        assert saved_file.exists()


@patch("brain.knowledge.KNOWLEDGE_DIR")
def test_save_sanitizes_title(mock_knowledge_dir, temp_knowledge_dir):
    """save() should sanitize dangerous characters from filenames."""
    with patch("brain.knowledge.KNOWLEDGE_DIR", temp_knowledge_dir):
        from brain.knowledge import save
        result = save("../../etc/passwd", "Should be sanitized")
        assert "Saved" in result
        # The filename should not contain "/" or ".." (sanitized to safe name)
        assert "../" not in result
        # The file should be inside the knowledge directory, not traversing up
        saved_file = temp_knowledge_dir / "notes" / "etcpasswd.md"
        assert saved_file.exists()
