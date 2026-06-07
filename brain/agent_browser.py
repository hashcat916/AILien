"""Agent Browser — AILIEN can discover, search for, and install new agents and skills.

This module acts as a registry browser, letting AILIEN:
- Search for capabilities (tools, skills, agents) on GitHub and the web
- Discover skills that match a specific task
- Install new skills from URLs or GitHub repositories
- List what's available to install
"""

import json
import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger("agent")

# ── Curation index ───────────────────────────────────────────────────────────
# Known skill/agent repositories and individual skills that can be installed.
# This is a community-curated index that AILIEN can query.

_KNOWN_SKILL_REPOS = [
    {
        "name": "AILIEN Community Skills",
        "type": "github",
        "url": "https://api.github.com/repos/ailien-community/skills/contents",
        "repo_url": "https://github.com/ailien-community/skills",
        "description": "Community-contributed skills for AILIEN",
    },
]

# Known individual skills (can be installed from raw URLs)
_KNOWN_SKILLS: list[dict[str, str]] = [
    # These are examples — users can add their own via the add_source tool
    {
        "name": "calculator",
        "description": "Advanced calculator with history and memory",
        "type": "builtin_example",
        "url": "",
    },
    {
        "name": "weather",
        "description": "Weather forecasting skill with multi-day outlook",
        "type": "builtin_example",
        "url": "",
    },
]

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "agent_browser"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_SOURCES_FILE = _CACHE_DIR / "sources.json"


# ── Source Management ────────────────────────────────────────────────────────

def _load_sources() -> list[dict[str, str]]:
    """Load user-added sources."""
    if _SOURCES_FILE.exists():
        try:
            return json.loads(_SOURCES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_sources(sources: list[dict[str, str]]) -> None:
    """Save user-added sources."""
    _SOURCES_FILE.write_text(json.dumps(sources, indent=2), encoding="utf-8")


# ── Searching for Capabilities ───────────────────────────────────────────────

def _search_github(query: str, max_results: int = 8) -> list[dict[str, str]]:
    """Search GitHub for repositories related to the query.

    Searches for Python-based automation tools, skills, and agents.
    """
    results = []
    search_queries = [
        f"{query} python skill automation",
        f"{query} ai agent tool",
        f"{query} python library",
    ]

    headers = {
        "User-Agent": "AILIEN-Agent-Browser/1.0",
        "Accept": "application/vnd.github.v3+json",
    }

    for sq in search_queries[:2]:  # Limit to 2 queries
        try:
            url = f"https://api.github.com/search/repositories?q={requests.utils.quote(sq)}+language:python&sort=stars&per_page={max_results}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.ok:
                data = resp.json()
                for item in data.get("items", []):
                    results.append({
                        "name": item["full_name"],
                        "description": item.get("description", "") or "",
                        "url": item["html_url"],
                        "stars": str(item.get("stargazers_count", 0)),
                        "source": "github",
                        "type": "repo",
                    })
            else:
                # GitHub API rate limited — fallback to search
                logger.debug("GitHub API returned %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.debug("GitHub search failed: %s", e)

    # Deduplicate by URL
    seen = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)
    return unique[:max_results]


def _search_web(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web for skills, tools, and agents related to the query."""
    results = []

    try:
        search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query + ' python tool or skill or agent')}"
        headers = {"User-Agent": "Mozilla/5.0 AILIEN-Browser/1.0"}
        resp = requests.get(search_url, headers=headers, timeout=10)

        if resp.ok:
            # Extract links using regex
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
                snippet = snippets[i] if i < len(snippets) else ""
                snippet = re.sub(r'<[^>]+>', '', snippet).strip()

                results.append({
                    "name": link.split("/")[2] if "//" in link else link[:50],
                    "description": snippet[:200] or "Web search result",
                    "url": link,
                    "source": "web",
                    "type": "web",
                })
    except Exception as e:
        logger.debug("Web search failed: %s", e)

    return results


# ── Installing Capabilities ──────────────────────────────────────────────────

def _validate_skill_source(source: str, skill_name: str) -> str | None:
    """Validate skill source code and return error message or None if OK."""
    # Check Python syntax
    try:
        compile(source, f"<{skill_name}>", "exec")
    except SyntaxError as e:
        return f"Syntax error: {e}"

    # Check it imports from skills
    if "import skills" not in source and "from skills" not in source:
        return "Skill must import from the skills module (e.g., 'from skills import Skill, tool' or 'import skills')"

    # Check it has a Skill subclass
    if "class " not in source or "Skill)" not in source:
        return "Skill must define a class that inherits from Skill"

    # Block dangerous patterns
    dangerous = ["os.system", "subprocess.Popen", "eval(", "exec(", "__import__"]
    for d in dangerous:
        if d in source:
            return f"Blocked dangerous pattern: {d}"

    return None


def install_skill_from_url(url: str) -> str:
    """Download and install a skill from a URL.

    Supports:
    - Raw GitHub URLs (raw.githubusercontent.com)
    - GitHub repository URLs
    - Direct download URLs for .py files
    """
    # Normalize GitHub URLs
    github_raw_match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/blob/(.+?)/(.+)",
        url,
    )
    if github_raw_match:
        user, repo, branch, path = github_raw_match.groups()
        url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}"

    # If it's a GitHub repo (not a file), list contents and try to find skills
    repo_match = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?$", url)
    if repo_match:
        user, repo = repo_match.groups()
        # Try to fetch the repo contents
        api_url = f"https://api.github.com/repos/{user}/{repo}/contents"
        try:
            headers = {"User-Agent": "AILIEN-Browser/1.0", "Accept": "application/vnd.github.v3+json"}
            resp = requests.get(api_url, headers=headers, timeout=10)
            if resp.ok:
                data = resp.json()
                # GitHub API returns list for directories, dict for single files
                if isinstance(data, dict):
                    data = [data]
                elif not isinstance(data, list):
                    return f"Unexpected response from GitHub API for '{user}/{repo}'."
                skill_files = [f for f in data if isinstance(f, dict) and f.get("name", "").endswith(".py") and f["name"] not in ("__init__.py",)]
                if not skill_files:
                    return f"Repository '{user}/{repo}' doesn't contain any Python skill files."
                if len(skill_files) == 1:
                    # Install the single skill
                    return install_skill_from_url(skill_files[0]["download_url"])
                else:
                    # List available skills
                    lines = [f"Repository '{user}/{repo}' contains multiple skills:"]
                    for sf in skill_files:
                        lines.append(f"  • {sf['name']} — install with:")
                        lines.append(f"    install_capability('{sf['download_url']}')")
                    return "\n".join(lines)
            return f"Could not access repository: {resp.status_code}"
        except Exception as e:
            return f"Error accessing repository: {e}"

    # Download the file
    try:
        headers = {"User-Agent": "AILIEN-Browser/1.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        if not resp.ok:
            return f"Failed to download from {url}: HTTP {resp.status_code}"
        source = resp.text
    except Exception as e:
        return f"Failed to download: {e}"

    # Determine skill name from URL or content
    skill_name = url.rstrip("/").split("/")[-1].replace(".py", "")
    if not skill_name or skill_name == url:
        skill_name = "downloaded_skill"

    # Validate
    error = _validate_skill_source(source, skill_name)
    if error:
        return f"Validation failed: {error}"

    # Save to skills directory
    try:
        _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        filepath = _SKILLS_DIR / f"{skill_name}.py"
        if filepath.exists():
            return f"Skill '{skill_name}' already exists. Remove it first or rename."

        filepath.write_text(source, encoding="utf-8")
        logger.info("Installed skill: %s from %s", skill_name, url)
    except Exception as e:
        return f"Failed to save skill file: {e}"

    # Try to load the skill
    try:
        # Add import to skills __init__.py triggers? No, skills/__init__.py loads
        # all modules in the skills directory on next startup.
        # For immediate loading, we use importlib
        spec = importlib.util.spec_from_file_location(f"skills.{skill_name}", filepath)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"skills.{skill_name}"] = mod
            spec.loader.exec_module(mod)

            # Discover and register any Skill subclasses
            from skills import Skill as SkillBase, _skills
            loaded_count = 0
            for obj_name in dir(mod):
                obj = getattr(mod, obj_name)
                if isinstance(obj, type) and issubclass(obj, SkillBase) and obj is not SkillBase:
                    instance = obj()
                    instance.on_load()
                    _skills[instance.name] = instance
                    loaded_count += 1

            if loaded_count > 0:
                return f"✅ Skill '{skill_name}' installed and loaded ({loaded_count} skill(s) registered). Available in the current session."
            else:
                return f"✅ Skill '{skill_name}' saved but no Skill subclass was auto-loaded. It will be available on next restart."
    except Exception as e:
        return f"✅ File saved but could not load dynamically: {e}. It will be available on next restart."


# ── Finding Missing Capabilities ─────────────────────────────────────────────

def _get_installed_tools_and_skills() -> dict[str, list[str]]:
    """Get all currently installed tools and skills."""
    # Get tools from the tool registry
    import tools as tools_module
    tool_names = tools_module.list_tools()

    # Get installed skills
    from skills import _skills as loaded_skills
    skill_names = list(loaded_skills.keys())

    # Get generated tools
    from brain.toolmaker import list_generated_tools as list_gen
    generated = list_gen()

    return {
        "tools": tool_names,
        "skills": skill_names,
        "generated": generated,
    }


# ── Import for dynamic loading ───────────────────────────────────────────────
import importlib.util
