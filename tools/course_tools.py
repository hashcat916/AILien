"""Course tools — find tutorials, build courses, generate offline books for coding and pentesting."""

from tools import tool


@tool(
    name="build_course",
    description="Build a complete learning course on a topic. Researches the web for tutorials, structures them into chapters and lessons, and saves everything for offline learning. Perfect for coding, pentesting, Linux, and tech topics.",
    params={
        "topic": {"type": "string", "description": "What to learn? Examples: 'Python for beginners', 'web security pentesting', 'SQL basics', 'Linux administration', 'JavaScript'"},
        "depth": {"type": "string", "description": "Course depth: 'beginner', 'intermediate', or 'advanced'", "enum": ["beginner", "intermediate", "advanced"], "default": "intermediate"},
    },
    required=["topic"],
)
def build_course(topic: str, depth: str = "intermediate") -> str:
    """Research and build a structured course on a topic."""
    from brain.course_builder import build_course as _build
    return _build(topic, depth)


@tool(
    name="generate_book",
    description="Generate an offline-ready book from a built course. Compiles all chapters and lessons into a single file you can read anywhere.",
    params={
        "topic": {"type": "string", "description": "The course topic to compile into a book (must have been built with build_course first)"},
        "format": {"type": "string", "description": "Output format:\n- 'markdown' — readable in any text editor, good for note-taking\n- 'html' — styled with dark mode support, open in a browser\n- 'txt' — plain text, loads on any device", "enum": ["markdown", "html", "txt"], "default": "markdown"},
    },
    required=["topic"],
)
def generate_book(topic: str, format: str = "markdown") -> str:
    """Compile a course into an offline book."""
    from brain.course_builder import generate_book as _gen
    return _gen(topic, format)


@tool(
    name="list_courses",
    description="List all built courses and generated books.",
    params={},
    required=[],
)
def list_courses() -> str:
    """List all saved courses and books."""
    from brain.course_builder import list_courses as _list
    return _list()


@tool(
    name="read_lesson",
    description="Read a specific lesson from a course you've built. Great for reviewing what you learned offline.",
    params={
        "topic": {"type": "string", "description": "The course topic (e.g. 'Python', 'Web Security')"},
        "chapter": {"type": "integer", "description": "Chapter number (1-based)", "default": 1},
        "lesson": {"type": "integer", "description": "Lesson number within the chapter (1-based)", "default": 1},
    },
    required=["topic"],
)
def read_lesson(topic: str, chapter: int = 1, lesson: int = 1) -> str:
    """Read a specific lesson from a course."""
    from brain.course_builder import read_lesson as _read
    return _read(topic, chapter, lesson)


@tool(
    name="find_tutorials",
    description="Search the web for coding or pentesting tutorials on a topic. Returns a list of useful links you can learn from or add to a course.",
    params={
        "topic": {"type": "string", "description": "What to find tutorials for? E.g. 'Python async', 'SQL injection', 'Linux bash scripting'"},
        "max_results": {"type": "integer", "description": "Maximum results to return (default 8)", "default": 8},
    },
    required=["topic"],
)
def find_tutorials(topic: str, max_results: int = 8) -> str:
    """Search the web for tutorials on a topic."""
    from brain.course_builder import _search_web

    # Build smart query with tutorial sources
    queries = [
        f"{topic} tutorial",
        f"{topic} guide for beginners",
        f"{topic} learn step by step",
    ]

    all_results = []
    seen_urls = set()

    for query in queries[:2]:
        results = _search_web(query, max_results=max_results)
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)

    if not all_results:
        return f"No tutorials found for '{topic}'. Try a different search term."

    lines = [f"🔍 Tutorials for: {topic}", ""]
    for i, r in enumerate(all_results[:max_results], 1):
        lines.append(f"  {i}. {r.get('title', 'Tutorial')}")
        if r.get("snippet"):
            lines.append(f"     {r['snippet'][:120]}")
        lines.append(f"     {r['url']}")
        lines.append("")

    lines.append("Tip: Use build_course to create a structured course from these resources.")

    return "\n".join(lines)
