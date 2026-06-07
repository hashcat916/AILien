"""Course Builder — finds coding and pentesting tutorials, structures them into courses, and generates offline books.

Turns web research into structured learning paths stored in the knowledge base.
Supports:
- Searching for tutorials on any topic
- Building structured courses with chapters and lessons
- Generating offline-ready books (Markdown/HTML)
- Exporting courses for offline reading
"""

import json
import logging
import re
import time
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger("agent")

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "courses"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_COURSES_INDEX = _CACHE_DIR / "courses_index.json"

_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AILIEN-CourseBuilder/1.0"

# ── Index Management ─────────────────────────────────────────────────────────

def _load_index() -> dict[str, Any]:
    """Load the courses index."""
    if _COURSES_INDEX.exists():
        try:
            return json.loads(_COURSES_INDEX.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"courses": [], "topics": {}}


def _save_index(index: dict[str, Any]) -> None:
    """Save the courses index."""
    _COURSES_INDEX.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── Web Search ───────────────────────────────────────────────────────────────

def _search_web(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web for tutorials on a topic."""
    results = []
    try:
        search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        headers = {"User-Agent": _USER_AGENT}
        resp = requests.get(search_url, headers=headers, timeout=10)

        if resp.ok:
            # Extract result links and snippets
            links = re.findall(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"', resp.text)
            snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)

            for i, link in enumerate(links[:max_results]):
                # Clean DuckDuckGo redirect URL
                if "uddg=" in link:
                    from urllib.parse import unquote, parse_qs, urlparse
                    parsed = urlparse(link)
                    qs = parse_qs(parsed.query)
                    actual = unquote(qs.get("uddg", [""])[0])
                    if actual:
                        link = actual

                title = link.split("/")[2] if "//" in link else link[:50]
                snippet = ""
                if i < len(snippets):
                    snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()

                results.append({
                    "title": title,
                    "url": link,
                    "snippet": snippet[:200],
                })
    except Exception as e:
        logger.debug("Web search failed: %s", e)

    return results


def _fetch_page_text(url: str, max_chars: int = 5000) -> str | None:
    """Fetch a URL and extract readable text content using brain.learner's extractor."""
    from brain.learner import _extract_text_from_html, _get_title_from_html

    try:
        resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=15)
        if not resp.ok:
            return None

        html = resp.text
        page_title = _get_title_from_html(html)
        text = _extract_text_from_html(html, max_chars=max_chars)

        if page_title:
            text = f"# {page_title}\n\n{text}"

        return text
    except Exception as e:
        logger.debug("Fetch failed for %s: %s", url, e)
        return None


# ── Course Building ──────────────────────────────────────────────────────────

def _generate_curriculum(topic: str, depth: str = "intermediate") -> list[dict[str, Any]]:
    """Generate a structured curriculum outline for a topic.

    Returns a list of chapters, each with a title and suggested lesson topics.
    This creates the skeleton — the actual content comes from web sources.
    """
    topic_lower = topic.lower()

    # Pre-built curriculum templates for common topics
    templates = {
        "python": [
            {"title": "Getting Started", "lessons": [
                "Installing Python and your first program",
                "Variables, data types, and basic operations",
                "Strings, numbers, and boolean logic",
            ]},
            {"title": "Control Flow", "lessons": [
                "Conditional statements (if/elif/else)",
                "Loops (for, while, break, continue)",
                "List comprehensions and generators",
            ]},
            {"title": "Functions and Modules", "lessons": [
                "Defining and calling functions",
                "Parameters, return values, and scope",
                "Importing and creating modules",
            ]},
            {"title": "Data Structures", "lessons": [
                "Lists, tuples, and sets",
                "Dictionaries and hash maps",
                "Stacks, queues, and linked lists",
            ]},
            {"title": "Object-Oriented Programming", "lessons": [
                "Classes, objects, and inheritance",
                "Magic methods and properties",
                "Abstract classes and interfaces",
            ]},
            {"title": "Advanced Topics", "lessons": [
                "File I/O and exception handling",
                "Decorators, context managers, and iterators",
                "Concurrency with threading and asyncio",
            ]},
        ],
        "javascript": [
            {"title": "JavaScript Fundamentals", "lessons": [
                "Variables, data types, and operators",
                "Functions and scope",
                "Objects, arrays, and JSON",
            ]},
            {"title": "DOM and Events", "lessons": [
                "Selecting and manipulating DOM elements",
                "Event handling and listeners",
                "Forms, inputs, and validation",
            ]},
            {"title": "Modern JavaScript", "lessons": [
                "ES6+ features: arrow functions, destructuring, spread",
                "Promises and async/await",
                "Modules and bundlers",
            ]},
            {"title": "Frameworks Overview", "lessons": [
                "React: components, state, and props",
                "Vue: reactivity and composition API",
                "Node.js: server-side JavaScript",
            ]},
        ],
        "sql": [
            {"title": "Database Basics", "lessons": [
                "What is a relational database?",
                "Tables, rows, and columns",
                "Primary keys and foreign keys",
            ]},
            {"title": "Querying Data", "lessons": [
                "SELECT statements and WHERE clauses",
                "JOINs: INNER, LEFT, RIGHT, FULL",
                "GROUP BY, HAVING, and aggregate functions",
            ]},
            {"title": "Data Modification", "lessons": [
                "INSERT, UPDATE, DELETE operations",
                "Transactions and ACID properties",
                "Indexes and query optimization",
            ]},
            {"title": "Advanced SQL", "lessons": [
                "Subqueries and CTEs",
                "Window functions and partitions",
                "Stored procedures and triggers",
            ]},
        ],
        "web security": [
            {"title": "Web Security Fundamentals", "lessons": [
                "HTTP protocol and security headers",
                "Authentication and session management",
                "Same-origin policy and CORS",
            ]},
            {"title": "Common Vulnerabilities", "lessons": [
                "Cross-Site Scripting (XSS)",
                "SQL Injection and parameterized queries",
                "Cross-Site Request Forgery (CSRF)",
            ]},
            {"title": "Authentication & Authorization", "lessons": [
                "OAuth 2.0 and OpenID Connect",
                "JWT tokens and API security",
                "Role-based access control (RBAC)",
            ]},
            {"title": "Network Security", "lessons": [
                "TLS/SSL and HTTPS",
                "Firewalls and intrusion detection",
                "VPNs and secure tunneling",
            ]},
            {"title": "Penetration Testing", "lessons": [
                "Reconnaissance and information gathering",
                "Vulnerability scanning tools",
                "Exploitation and post-exploitation",
            ]},
        ],
        "linux": [
            {"title": "Linux Fundamentals", "lessons": [
                "The Linux filesystem and navigation",
                "File permissions and ownership",
                "Process management and signals",
            ]},
            {"title": "Shell Scripting", "lessons": [
                "Bash basics: variables, conditionals, loops",
                "Text processing with grep, sed, awk",
                "Automation with cron and systemd",
            ]},
            {"title": "System Administration", "lessons": [
                "User and group management",
                "Package management (apt, yum, pacman)",
                "Logging and monitoring",
            ]},
            {"title": "Networking", "lessons": [
                "Network configuration and tools",
                "Firewall management with iptables/nftables",
                "SSH, SCP, and remote administration",
            ]},
            {"title": "Security Hardening", "lessons": [
                "SELinux and AppArmor",
                "Auditing with auditd and Lynis",
                "Intrusion detection with fail2ban",
            ]},
        ],
        "pentesting": [
            {"title": "Reconnaissance", "lessons": [
                "Passive reconnaissance with OSINT",
                "Active scanning with Nmap",
                "Subdomain enumeration and DNS recon",
            ]},
            {"title": "Vulnerability Assessment", "lessons": [
                "Automated scanning with Nessus/OpenVAS",
                "Manual testing techniques",
                "Common vulnerability scoring (CVSS)",
            ]},
            {"title": "Web Application Testing", "lessons": [
                "Burp Suite fundamentals",
                "XSS, SQLi, and CSRF exploitation",
                "API and GraphQL testing",
            ]},
            {"title": "Network Exploitation", "lessons": [
                "Metasploit fundamentals",
                "Password attacks and hash cracking",
                "Pivoting and lateral movement",
            ]},
            {"title": "Post-Exploitation", "lessons": [
                "Privilege escalation (Linux/Windows)",
                "Persistence mechanisms",
                "Covering tracks and logging",
            ]},
            {"title": "Reporting", "lessons": [
                "Writing penetration test reports",
                "Risk assessment and remediation",
                "Legal and ethical considerations",
            ]},
        ],
    }

    # Try to match the topic to a template
    best_match = None
    for key, curriculum in templates.items():
        if key in topic_lower or topic_lower in key:
            best_match = curriculum
            break

    if best_match:
        return best_match

    # Generic curriculum for any topic
    return [
        {"title": f"Introduction to {topic.title()}", "lessons": [
            f"What is {topic}?",
            f"Getting started with {topic}",
            f"Core concepts and terminology",
        ]},
        {"title": "Fundamentals", "lessons": [
            f"Basic principles of {topic}",
            f"Essential tools and setup",
            f"First practical exercise",
        ]},
        {"title": "Intermediate Concepts", "lessons": [
            f"Building on the basics",
            f"Real-world examples",
            f"Common patterns and best practices",
        ]},
        {"title": "Advanced Topics", "lessons": [
            f"Deep dive into {topic}",
            f"Advanced techniques",
            f"Performance and optimization",
        ]},
        {"title": "Practice and Projects", "lessons": [
            f"Hands-on exercises",
            f"Building a complete project",
            f"Review and next steps",
        ]},
    ]


def _search_lesson_content(lesson_title: str, topic: str) -> str:
    """Search the web for lesson content and return combined text."""
    from brain.learner import _extract_text_from_html

    combined_content = []
    seen_urls = set()

    queries = [f"{lesson_title} {topic} tutorial", f"{lesson_title} {topic} guide"]

    for query in queries:
        results = _search_web(query, max_results=3)
        for r in results:
            url = r["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)

            try:
                resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=15)
                if resp.ok:
                    text = _extract_text_from_html(resp.text, max_chars=3000)
                    if text and len(text) > 200:
                        combined_content.append(f"\n## Source: {url}\n\n{text}")
                        break
            except Exception:
                pass

            time.sleep(0.3)  # Throttle requests

    if not combined_content:
        return ""

    return "\n\n---\n\n".join(combined_content[:2])


def _generate_lesson_summary(content: str) -> str:
    """Generate a concise summary from lesson content."""
    # Extract first meaningful paragraph
    paragraphs = re.split(r'\n\s*\n', content)
    meaningful = [p for p in paragraphs if len(p.strip()) > 100]
    if meaningful:
        return meaningful[0][:500]
    return content[:500] if content else ""


def build_course(topic: str, depth: str = "intermediate", num_sources_per_lesson: int = 2) -> str:
    """Build a complete course on a topic.

    Steps:
    1. Generate curriculum outline
    2. Search for lesson content from the web
    3. Summarize each lesson
    4. Save to the knowledge base

    Returns a status message.
    """
    logger.info("Building course on: %s", topic)

    # 1. Generate curriculum
    curriculum = _generate_curriculum(topic, depth)
    total_lessons = sum(len(ch["lessons"]) for ch in curriculum)

    # 2. Search and fetch content for each lesson
    course_data = {
        "title": topic.title(),
        "description": f"A {depth} level course on {topic}",
        "difficulty": depth,
        "built_at": datetime.now().isoformat(),
        "total_lessons": total_lessons,
        "chapters": [],
    }

    for ch_idx, chapter in enumerate(curriculum):
        chapter_data = {
            "title": chapter["title"],
            "lessons": [],
        }

        for lesson_title in chapter["lessons"]:
            logger.info("  Researching: %s", lesson_title)

            # Search and fetch content
            content = _search_lesson_content(lesson_title, topic)
            summary = _generate_lesson_summary(content) if content else ""

            lesson_data = {
                "title": lesson_title,
                "summary": summary[:500] if summary else "Content not found — try generating offline content.",
                "content": content if content else "Content not yet available. Use generate_book to compile.",
                "key_points": _extract_key_points(content) if content else [],
            }
            chapter_data["lessons"].append(lesson_data)

        course_data["chapters"].append(chapter_data)

    # 3. Save to knowledge base
    try:
        from brain.knowledge import save as kb_save

        # Save as JSON for the course system
        course_file = _CACHE_DIR / f"{topic.lower().replace(' ', '_')}_course.json"
        course_file.write_text(json.dumps(course_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Also save a markdown summary to the knowledge base
        md = _course_to_markdown(course_data)
        kb_save(f"Course: {topic.title()}", md, category="topics")

        # Update index
        index = _load_index()
        index["courses"].append({
            "topic": topic.title(),
            "difficulty": depth,
            "chapters": len(curriculum),
            "lessons": total_lessons,
            "built_at": datetime.now().isoformat(),
        })
        index["topics"][topic.lower()] = {"built": datetime.now().isoformat()}
        _save_index(index)

        logger.info("Course built: %s (%d chapters, %d lessons)", topic, len(curriculum), total_lessons)

        return (
            f"✅ Course built: {topic.title()}\n"
            f"   Difficulty: {depth}\n"
            f"   {len(curriculum)} chapters, {total_lessons} lessons\n"
            f"   Saved to knowledge base and course cache\n"
            f"\n"
            f"Next steps:\n"
            f"  • generate_book('{topic}', format='markdown') — compile into a book\n"
            f"  • export_course('{topic}', format='html') — export as HTML\n"
            f"  • list_courses() — show all your courses"
        )

    except Exception as e:
        return f"Course built but failed to save: {e}"


def _extract_key_points(text: str, max_points: int = 5) -> list[str]:
    """Extract key points from lesson content."""
    points = []
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        # Look for bullet points, numbered lists, or key statements
        if line.startswith("•") or line.startswith("-") or line.startswith("*"):
            points.append(line.lstrip("•-* ").strip()[:150])
        elif line.startswith(("1.", "2.", "3.", "4.", "5.")):
            points.append(line.split(".", 1)[-1].strip()[:150])
        if len(points) >= max_points:
            break

    if not points and text:
        # Fallback: use sentences with key markers
        sentences = re.split(r'[.!?]+', text)
        key_markers = ["important", "key", "essential", "always", "never", "must",
                       "critical", "fundamental", "best practice", "warning"]
        for s in sentences:
            if any(m in s.lower() for m in key_markers):
                points.append(s.strip()[:150])
                if len(points) >= max_points:
                    break

    return points


def _course_to_markdown(course: dict) -> str:
    """Convert a course to structured markdown."""
    lines = [
        f"# {course['title']}",
        f"",
        f"**Difficulty**: {course.get('difficulty', 'N/A')}",
        f"**Lessons**: {course.get('total_lessons', 'N/A')}",
        f"**Built**: {course.get('built_at', '')[:10]}",
        f"",
        f"---",
        f"",
    ]

    for ch_idx, chapter in enumerate(course.get("chapters", []), 1):
        lines.append(f"## Chapter {ch_idx}: {chapter['title']}")
        lines.append("")

        for lesson in chapter.get("lessons", []):
            lines.append(f"### {lesson['title']}")
            if lesson.get("summary"):
                lines.append(f"")
                lines.append(lesson["summary"])
            if lesson.get("key_points"):
                lines.append(f"")
                lines.append("**Key Points:**")
                for pt in lesson["key_points"]:
                    lines.append(f"- {pt}")
            lines.append("")

    return "\n".join(lines)


# ── Book Generation ──────────────────────────────────────────────────────────

def generate_book(topic: str, format: str = "markdown") -> str:
    """Generate a full book from a saved course.

    Compiles all chapters and lessons into a single structured document
    suitable for offline reading or printing.

    Args:
        topic: The course topic to compile
        format: 'markdown', 'html', or 'txt'

    Returns:
        Path to the generated book file.
    """
    # Load the course
    course_file = _CACHE_DIR / f"{topic.lower().replace(' ', '_')}_course.json"
    if not course_file.exists():
        return f"Course '{topic}' not found. Use build_course('{topic}') first."

    try:
        course = json.loads(course_file.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Could not load course: {e}"

    book_dir = _CACHE_DIR / "books"
    book_dir.mkdir(parents=True, exist_ok=True)
    safe_name = topic.lower().replace(" ", "_").replace("/", "_")
    format = format.lower()

    if format == "html":
        return _generate_html_book(course, book_dir, safe_name)
    elif format == "txt":
        return _generate_txt_book(course, book_dir, safe_name)
    else:
        return _generate_markdown_book(course, book_dir, safe_name)


def _generate_markdown_book(course: dict, book_dir: Path, safe_name: str) -> str:
    """Generate a full Markdown book."""
    lines = [
        f"# {course['title']} — Complete Course",
        f"",
        f"**Difficulty**: {course.get('difficulty', 'N/A')}",
        f"**Total Lessons**: {course.get('total_lessons', 'N/A')}",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"---",
        f"## Table of Contents",
        f"",
    ]

    # Table of Contents
    for ch_idx, chapter in enumerate(course.get("chapters", []), 1):
        lines.append(f"{ch_idx}. **{chapter['title']}**")
        for lesson in chapter.get("lessons", []):
            lines.append(f"   - {lesson['title']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Content
    for ch_idx, chapter in enumerate(course.get("chapters", []), 1):
        lines.append(f"# Chapter {ch_idx}: {chapter['title']}")
        lines.append("")

        for lesson in chapter.get("lessons", []):
            lines.append(f"## {lesson['title']}")
            lines.append("")

            if lesson.get("summary"):
                lines.append(lesson["summary"])
                lines.append("")

            if lesson.get("key_points"):
                lines.append("### Key Points")
                for pt in lesson["key_points"]:
                    lines.append(f"- {pt}")
                lines.append("")

            if lesson.get("content"):
                lines.append("### Content")
                lines.append("")
                lines.append(lesson["content"])
                lines.append("")
                lines.append("---")
                lines.append("")

    book_path = book_dir / f"{safe_name}_book.md"
    book_path.write_text("\n".join(lines), encoding="utf-8")

    total_chars = len("\n".join(lines))
    return (
        f"📖 Book generated: {book_path}\n"
        f"   Format: Markdown\n"
        f"   Size: ~{total_chars:,} characters\n"
        f"   Chapters: {len(course.get('chapters', []))}\n"
        f"   Ready for offline reading or conversion to PDF."
    )


def _generate_html_book(course: dict, book_dir: Path, safe_name: str) -> str:
    """Generate an HTML book with styling."""
    chapters_html = []

    for ch_idx, chapter in enumerate(course.get("chapters", []), 1):
        lessons_html = []
        for lesson in chapter.get("lessons", []):
            content = lesson.get("content", "").replace("\n", "<br>\n")
            key_points = ""
            if lesson.get("key_points"):
                points = "\n".join(f"      <li>{p}</li>" for p in lesson["key_points"])
                key_points = f"""
      <h3>Key Points</h3>
      <ul>
{points}
      </ul>"""

            lessons_html.append(f"""
    <div class="lesson">
      <h3>{lesson['title']}</h3>
      {key_points}
      <div class="content">
        {content}
      </div>
    </div>""")

        chapters_html.append(f"""
  <div class="chapter">
    <h2>Chapter {ch_idx}: {chapter['title']}</h2>
    {''.join(lessons_html)}
  </div>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{course['title']} — Course Book</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 2em; line-height: 1.6; color: #333; }}
    h1 {{ color: #1a1a2e; border-bottom: 2px solid #e94560; padding-bottom: 0.3em; }}
    h2 {{ color: #16213e; margin-top: 2em; }}
    h3 {{ color: #0f3460; }}
    .chapter {{ margin-bottom: 3em; }}
    .lesson {{ margin-left: 1em; margin-bottom: 2em; padding: 1em; background: #f8f9fa; border-radius: 8px; }}
    .content {{ margin-top: 1em; }}
    .toc {{ background: #eef; padding: 1em; border-radius: 8px; }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #1a1a2e; color: #eee; }}
      h1 {{ color: #e94560; }}
      h2 {{ color: #f5a623; }}
      h3 {{ color: #4cc9f0; }}
      .lesson {{ background: #16213e; }}
      .toc {{ background: #0f3460; }}
    }}
  </style>
</head>
<body>
  <h1>{course['title']} — Complete Course</h1>
  <p><strong>Difficulty:</strong> {course.get('difficulty', 'N/A')} |
     <strong>Lessons:</strong> {course.get('total_lessons', 'N/A')} |
     <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

  <div class="toc">
    <h2>Table of Contents</h2>
    <ol>
"""
    for ch_idx, chapter in enumerate(course.get("chapters", []), 1):
        html += f"      <li><strong>{chapter['title']}</strong><ul>\n"
        for lesson in chapter.get("lessons", []):
            html += f"        <li>{lesson['title']}</li>\n"
        html += "      </ul></li>\n"
    html += "    </ol>\n  </div>\n"

    html += "".join(chapters_html)
    html += "\n</body>\n</html>"

    book_path = book_dir / f"{safe_name}_book.html"
    book_path.write_text(html, encoding="utf-8")

    return (
        f"📖 Book generated: {book_path}\n"
        f"   Format: HTML (stylized, dark-mode ready)\n"
        f"   Size: ~{len(html):,} characters\n"
        f"   Open in any browser for offline reading."
    )


def _generate_txt_book(course: dict, book_dir: Path, safe_name: str) -> str:
    """Generate a plain text book (minimal, loads anywhere)."""
    lines = [
        f"{'=' * 60}",
        f"{course['title']} — Complete Course".center(60),
        f"{'=' * 60}",
        f"",
        f"Difficulty: {course.get('difficulty', 'N/A')}",
        f"Total Lessons: {course.get('total_lessons', 'N/A')}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"{'=' * 60}",
        f"TABLE OF CONTENTS",
        f"{'=' * 60}",
        f"",
    ]

    # Table of Contents
    for ch_idx, chapter in enumerate(course.get("chapters", []), 1):
        lines.append(f"Chapter {ch_idx}: {chapter['title']}")
        for lesson in chapter.get("lessons", []):
            lines.append(f"    - {lesson['title']}")
    lines.append("")
    lines.append("=" * 60)
    lines.append("")

    # Content
    for ch_idx, chapter in enumerate(course.get("chapters", []), 1):
        lines.append(f"{'=' * 60}")
        lines.append(f"CHAPTER {ch_idx}: {chapter['title']}")
        lines.append(f"{'=' * 60}")
        lines.append("")

        for lesson in chapter.get("lessons", []):
            lines.append(f"{'-' * 40}")
            lines.append(f"Lesson: {lesson['title']}")
            lines.append(f"{'-' * 40}")
            lines.append("")

            if lesson.get("summary"):
                text = lesson["summary"]
                lines.append(text)
                lines.append("")

            if lesson.get("key_points"):
                lines.append("Key Points:")
                for pt in lesson["key_points"]:
                    lines.append(f"  * {pt}")
                lines.append("")

            if lesson.get("content"):
                text = lesson["content"]
                lines.append(text)
                lines.append("")

    book_path = book_dir / f"{safe_name}_book.txt"
    book_path.write_text("\n".join(lines), encoding="utf-8")

    return (
        f"📖 Book generated: {book_path}\n"
        f"   Format: Plain Text\n"
        f"   Size: ~{len('\n'.join(lines)):,} characters\n"
        f"   Opens on any device."
    )


# ── Course Listing ───────────────────────────────────────────────────────────

def list_courses() -> str:
    """List all saved courses."""
    index = _load_index()
    courses = index.get("courses", [])

    if not courses:
        return "No courses built yet. Use build_course('topic') to create one."

    lines = ["📚 Your Learning Courses:", ""]
    for c in courses:
        lines.append(f"  • {c['topic']} ({c['difficulty']})")
        lines.append(f"    {c['chapters']} chapters, {c['lessons']} lessons — built {c['built_at'][:10]}")
        lines.append("")

    # Also list any book files
    book_dir = _CACHE_DIR / "books"
    if book_dir.exists():
        books = list(book_dir.glob("*"))
        if books:
            lines.append("📖 Generated books:")
            for b in sorted(books):
                size = b.stat().st_size
                if size > 1024:
                    size_str = f"{size // 1024}KB"
                else:
                    size_str = f"{size}B"
                lines.append(f"  • {b.name} ({size_str})")

    return "\n".join(lines)


def read_lesson(topic: str, chapter: int = 1, lesson: int = 1) -> str:
    """Read a specific lesson from a course."""
    course_file = _CACHE_DIR / f"{topic.lower().replace(' ', '_')}_course.json"
    if not course_file.exists():
        return f"Course '{topic}' not found. Use build_course('{topic}') first."

    try:
        course = json.loads(course_file.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Could not load course: {e}"

    chapters = course.get("chapters", [])
    if chapter < 1 or chapter > len(chapters):
        return f"Chapter {chapter} out of range. Course has {len(chapters)} chapters."

    ch = chapters[chapter - 1]
    lessons = ch.get("lessons", [])
    if lesson < 1 or lesson > len(lessons):
        return f"Lesson {lesson} out of range. Chapter has {len(lessons)} lessons."

    les = lessons[lesson - 1]
    content = les.get("content", "No content available.")
    summary = les.get("summary", "")
    key_points = les.get("key_points", [])

    lines = [
        f"📖 {course['title']} — Chapter {chapter}: {ch['title']}",
        f"   Lesson {lesson}: {les['title']}",
        "",
    ]
    if summary:
        lines.append(summary)
        lines.append("")

    if key_points:
        lines.append("Key Points:")
        for pt in key_points:
            lines.append(f"  • {pt}")
        lines.append("")

    if content and len(content) > 500:
        lines.append(content[:3000])
        if len(content) > 3000:
            lines.append("\n... (content truncated)")
    elif content:
        lines.append(content)

    return "\n".join(lines)
