"""Agent Browser tools — AILIEN can search for and install new agents and skills from GitHub and the web."""

import logging

from tools import tool

logger = logging.getLogger("agent")


@tool(
    name="search_capabilities",
    description="Search for tools, agents, or skills that can perform a specific task. Searches GitHub and the web for relevant capabilities. Use this when you need a capability you don't have.",
    params={
        "query": {"type": "string", "description": "What capability are you looking for? E.g. 'image processing', 'send email', 'web scraping', 'calendar management'"},
        "max_results": {"type": "integer", "description": "Maximum results to return (default 8)", "default": 8},
    },
    required=["query"],
)
def search_capabilities(query: str, max_results: int = 8) -> str:
    """Search for tools, agents, and skills that match a capability need."""
    from brain.agent_browser import _search_github, _search_web

    results = []
    results.extend(_search_github(query, max_results=max_results))
    results.extend(_search_web(query, max_results=max_results))

    if not results:
        return (
            f"No capabilities found matching '{query}'.\n\n"
            f"You can try:\n"
            f"  • A more specific search query\n"
            f"  • Creating the tool yourself with create_tool\n"
            f"  • Learning how to build it with learn_from_web"
        )

    lines = [f"🔍 Capabilities for: {query}", ""]
    for i, r in enumerate(results, 1):
        source_icon = "🐙" if r.get("source") == "github" else "🌐"
        stars = f" ⭐{r['stars']}" if r.get("stars") and r["stars"] != "0" else ""
        lines.append(f"  {i}. {source_icon} {r['name']}{stars}")
        lines.append(f"     {r.get('description', 'No description')[:120]}")
        lines.append(f"     {r['url']}")
        lines.append("")

    lines.append(f"\nTo install: install_capability(url=<url>)")

    return "\n".join(lines)


@tool(
    name="install_capability",
    description="Install a new skill or capability from a URL (GitHub repo, raw .py file, or community source). After installation, the skill is immediately available.",
    params={
        "url": {"type": "string", "description": "URL to install from. Supports:\n- GitHub repos: https://github.com/user/repo\n- Raw Python files: https://raw.githubusercontent.com/user/repo/main/skill.py\n- Direct .py file URLs"},
    },
    required=["url"],
)
def install_capability(url: str) -> str:
    """Install a skill from a URL."""
    from brain.agent_browser import install_skill_from_url

    # Basic URL validation
    if not url.startswith(("http://", "https://")):
        return "Please provide a full URL starting with http:// or https://"

    result = install_skill_from_url(url)

    return result


@tool(
    name="list_available_capabilities",
    description="List all known capability sources and what's available to install. Shows community repos and user-added sources.",
    params={},
    required=[],
)
def list_available_capabilities() -> str:
    """List known sources and what's available to install."""
    from brain.agent_browser import _KNOWN_SKILL_REPOS, _KNOWN_SKILLS, _load_sources, _get_installed_tools_and_skills

    installed = _get_installed_tools_and_skills()
    user_sources = _load_sources()

    lines = ["📦 Capability Sources", ""]

    # Installed tools/skills
    lines.append("Currently installed:")
    lines.append(f"  • {len(installed['tools'])} built-in tools")
    lines.append(f"  • {len(installed['skills'])} skill(s)")
    lines.append(f"  • {len(installed['generated'])} custom generated tool(s)")
    lines.append("")

    # Community repos
    lines.append("Community repos (install with install_capability):")
    for repo in _KNOWN_SKILL_REPOS:
        lines.append(f"  • {repo['name']} — {repo['description']}")
        lines.append(f"    {repo['repo_url']}")
    lines.append("")

    # Individual known skills
    if _KNOWN_SKILLS:
        lines.append("Individual skills:")
        for skill in _KNOWN_SKILLS:
            lines.append(f"  • {skill['name']} — {skill['description']}")
        lines.append("")

    # User-added sources
    if user_sources:
        lines.append("Your custom sources:")
        for src in user_sources:
            lines.append(f"  • {src.get('name', 'Unnamed')} — {src.get('url', '')}")
        lines.append("")

    if not _KNOWN_SKILL_REPOS and not _KNOWN_SKILLS and not user_sources:
        lines.append("No capability sources configured yet.")
        lines.append("Use search_capabilities to find tools on GitHub, or add sources manually.")

    lines.append("")
    lines.append("Usage:")
    lines.append("  • search_capabilities('send email') — search for capabilities")
    lines.append("  • install_capability(url) — install from GitHub or raw URL")

    return "\n".join(lines)


@tool(
    name="find_missing_capability",
    description="When you need a capability you don't have, call this to find an existing tool or skill. It will search installed tools, available sources, and the web.",
    params={
        "task": {"type": "string", "description": "Describe what you need to do, e.g. 'send an email with attachment', 'parse a CSV file', 'control Spotify'"},
    },
    required=["task"],
)
def find_missing_capability(task: str) -> str:
    """Find a capability for a specific task — check installed tools first, then search."""
    from brain.agent_browser import _get_installed_tools_and_skills, _search_github, _search_web

    installed = _get_installed_tools_and_skills()

    # Check if any existing tool matches
    all_installed = installed["tools"] + [
        f"skill_{s}" for s in installed["skills"]
    ] + installed["generated"]

    # Keyword matching against task (skip short words to avoid noise)
    task_lower = task.lower()
    task_words = {w for w in task_lower.split() if len(w) >= 4}
    matching_tools = []
    for t in all_installed:
        t_clean = t.replace("_", " ").replace("-", " ")
        t_words = set(t_clean.split())
        if task_words & t_words:  # intersection — any word matches
            matching_tools.append(t)

    lines = [f"🔎 Looking for: {task}", ""]

    if matching_tools:
        lines.append("✅ Already have these relevant capabilities:")
        for t in sorted(matching_tools)[:5]:
            lines.append(f"  • {t}")
        lines.append("")
        if len(matching_tools) > 5:
            lines.append(f"  ... and {len(matching_tools) - 5} more")
            lines.append("")

    # Search the web for new capabilities
    lines.append("Searching for new capabilities...")
    results = []
    results.extend(_search_github(task, max_results=4))
    results.extend(_search_web(task, max_results=3))

    if results:
        lines.append("")
        lines.append("Found these potential capabilities:")
        for i, r in enumerate(results[:5], 1):
            source_icon = "🐙" if r.get("source") == "github" else "🌐"
            lines.append(f"  {i}. {source_icon} {r['name']}")
            lines.append(f"     {r.get('description', '')[:100]}")
            lines.append(f"     Install: install_capability('{r['url']}')")
            lines.append("")

    if not matching_tools and not results:
        lines.append("Couldn't find an existing capability.")
        lines.append("You can:")
        lines.append(f"  • Create a new tool with create_tool")
        lines.append(f"  • Learn how to implement it with learn_from_web")
        lines.append(f"  • Try a more specific search with search_capabilities")

    return "\n".join(lines)
