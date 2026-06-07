"""Project analysis and user preferences tools.

project_analyze — One-shot deep scan of any project directory.
user_preferences — Save and recall your preferences across projects.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from tools import tool

_PROJECT_DIR = Path(__file__).resolve().parent.parent
_PREFS_FILE = _PROJECT_DIR / ".cache" / "user_preferences.json"


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

def _load_prefs() -> dict[str, Any]:
    """Load user preferences from cache."""
    try:
        if _PREFS_FILE.exists():
            return json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"preferences": {}, "saved_at": None}


def _save_prefs(prefs: dict[str, Any]) -> None:
    """Save user preferences."""
    _PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    prefs["saved_at"] = datetime.now().isoformat()
    _PREFS_FILE.write_text(json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8")


@tool(
    name="save_preference",
    description="Remember a user preference or convention for future sessions. Use this to save how the user likes things done (package manager, testing framework, naming conventions, formatting, etc.)",
    params={
        "key": {"type": "string", "description": "Preference key, e.g. 'package_manager', 'test_framework', 'naming_convention', 'indent_style'"},
        "value": {"type": "string", "description": "Preference value, e.g. 'pnpm', 'pytest', 'snake_case', 'tabs'"},
        "context": {"type": "string", "description": "Optional context about when this preference applies, e.g. 'for Python projects', 'for web projects'", "default": ""},
    },
    required=["key", "value"],
)
def save_preference(key: str, value: str, context: str = "") -> str:
    """Save a user preference for future sessions."""
    prefs = _load_prefs()
    entry = {"value": value, "saved_at": datetime.now().isoformat()}
    if context:
        entry["context"] = context
    prefs["preferences"][key.lower().strip()] = entry
    _save_prefs(prefs)
    return f"Saved preference: {key} = {value}"


@tool(
    name="get_preferences",
    description="Recall saved user preferences. Optionally filter by key or search term.",
    params={
        "key": {"type": "string", "description": "Optional specific preference key to look up (e.g. 'package_manager')", "default": ""},
        "search": {"type": "string", "description": "Optional search term to find preferences by context or value", "default": ""},
    },
    required=[],
)
def get_preferences(key: str = "", search: str = "") -> str:
    """Recall saved user preferences."""
    prefs = _load_prefs()
    all_prefs = prefs.get("preferences", {})

    if not all_prefs:
        return "No preferences saved yet. Use 'save_preference' to remember something."

    if key:
        key = key.lower().strip()
        if key in all_prefs:
            entry = all_prefs[key]
            lines = [f"  {key} = {entry['value']}"]
            if entry.get("context"):
                lines.append(f"    Context: {entry['context']}")
            lines.append(f"    Saved: {entry['saved_at'][:10]}")
            return "\n".join(lines)
        return f"No preference found for '{key}'."

    if search:
        search_lower = search.lower()
        matches = {k: v for k, v in all_prefs.items()
                   if search_lower in k or search_lower in v.get("value", "").lower()
                   or search_lower in v.get("context", "").lower()}
        if not matches:
            return f"No preferences matching '{search}'."
        all_prefs = matches

    lines = [f"Saved preferences ({len(all_prefs)}):"]
    for k, v in sorted(all_prefs.items()):
        lines.append(f"  • {k} = {v['value']}")
        if v.get("context"):
            lines.append(f"    ({v['context']})")
    return "\n".join(lines)


@tool(
    name="remove_preference",
    description="Remove a saved user preference by key.",
    params={
        "key": {"type": "string", "description": "Preference key to remove"},
    },
    required=["key"],
)
def remove_preference(key: str) -> str:
    """Remove a saved preference."""
    prefs = _load_prefs()
    key = key.lower().strip()
    if key in prefs.get("preferences", {}):
        del prefs["preferences"][key]
        _save_prefs(prefs)
        return f"Removed preference: {key}"
    return f"No preference found for '{key}'."


# ---------------------------------------------------------------------------
# Project analysis
# ---------------------------------------------------------------------------

@tool(
    name="project_analyze",
    description="Deep-scan any project directory and return a comprehensive overview: language, dependencies, structure, entry points, test patterns, conventions, and more. Use this to quickly understand any new project.",
    params={
        "directory": {"type": "string", "description": "Path to the project directory to analyze (default: current directory)", "default": "."},
        "include_dev_deps": {"type": "boolean", "description": "Whether to include dev dependencies in the output (default: false)", "default": False},
    },
    required=[],
)
def project_analyze(directory: str = ".", include_dev_deps: bool = False) -> str:
    """Deep-scan a project directory and return a comprehensive overview."""
    try:
        root = Path(directory).expanduser().resolve()
        if not root.is_dir():
            return f"Directory does not exist: {root}"
    except Exception as e:
        return f"Invalid path: {e}"

    # --- 1. Project name & description ---
    name = root.name

    # --- 2. Detect language & frameworks ---
    info = _detect_language(root)

    # --- 3. Dependencies ---
    deps_info = _detect_dependencies(root, include_dev_deps)

    # --- 4. Project structure ---
    structure = _analyze_structure(root)

    # --- 5. Entry points ---
    entry_points = _find_entry_points(root, info.get("language", ""))

    # --- 6. Test patterns ---
    test_info = _detect_test_patterns(root)

    # --- 7. Git info ---
    git_info = _get_git_info(root)

    # --- 8. Conventions ---
    conventions = _detect_conventions(root, info.get("language", ""))

    # --- Build output ---
    lines = [
        f"╔══════════════════════════════════════════════╗",
        f"║  Project: {name:<47}║",
        f"╚══════════════════════════════════════════════╝",
        f"",
        f"📁 Path: {root}",
        f"",
    ]

    # Language
    lang = info.get("language", "Unknown")
    framework = info.get("framework", "")
    lines.append(f"🔤 Language: {lang}")
    if framework:
        lines.append(f"   Framework: {framework}")
    if info.get("version"):
        lines.append(f"   Version: {info['version']}")
    lines.append("")

    # Dependencies
    if deps_info:
        lines.append(f"📦 Package Manager: {deps_info.get('manager', 'None detected')}")
        if deps_info.get("runtimes"):
            lines.append(f"   Runtime: {deps_info['runtimes']}")
        runtime_deps = deps_info.get("runtime_deps", [])
        if runtime_deps:
            lines.append(f"   Runtime deps ({len(runtime_deps)}): {', '.join(runtime_deps[:12])}")
            if len(runtime_deps) > 12:
                lines[-1] += f" (+{len(runtime_deps) - 12} more)"
        dev_deps = deps_info.get("dev_deps", [])
        if dev_deps and include_dev_deps:
            lines.append(f"   Dev deps ({len(dev_deps)}): {', '.join(dev_deps[:8])}")
            if len(dev_deps) > 8:
                lines[-1] += f" (+{len(dev_deps) - 8} more)"
        lines.append("")

    # Structure
    lines.append(f"📂 Structure ({structure.get('file_count', 0)} files):")
    for item in structure.get("top_dirs", [])[:10]:
        lines.append(f"   📁 {item}")
    for item in structure.get("key_files", [])[:8]:
        lines.append(f"   📄 {item}")
    if structure.get("file_types"):
        lines.append(f"   File types: {', '.join(structure['file_types'][:8])}")
    lines.append("")

    # Entry points
    if entry_points:
        lines.append(f"🚪 Entry Points:")
        for ep in entry_points[:5]:
            lines.append(f"   {ep}")
        lines.append("")

    # Tests
    if test_info:
        lines.append(f"🧪 Testing:")
        lines.append(f"   Framework: {test_info.get('framework', 'Unknown')}")
        lines.append(f"   Test files: {test_info.get('count', 0)}")
        if test_info.get("command"):
            lines.append(f"   Run with: {test_info['command']}")
        lines.append("")

    # Git
    if git_info:
        lines.append(f"🔧 Git:")
        lines.append(f"   Branch: {git_info.get('branch', 'unknown')}")
        if git_info.get("last_commit"):
            lines.append(f"   Last commit: {git_info['last_commit']}")
        lines.append("")

    # Conventions
    if conventions:
        lines.append(f"📐 Conventions detected:")
        for c in conventions[:8]:
            lines.append(f"   • {c}")
        lines.append("")

    # Save analysis to knowledge base for future reference
    try:
        from brain.knowledge import save as kb_save
        content = f"# Project Analysis: {name}\n\n{chr(10).join(lines)}"
        kb_save(f"Project_{name}", content, category="topics")
    except Exception:
        pass

    return "\n".join(lines)


def _detect_language(root: Path) -> dict[str, str]:
    """Detect the primary language and framework of a project."""
    result = {"language": "Unknown", "framework": "", "version": ""}

    # Check for config files that indicate language
    checks = [
        "package.json", "pyproject.toml", "requirements.txt", "setup.py",
        "Cargo.toml", "go.mod", "build.gradle", "pom.xml",
        "CMakeLists.txt", "composer.json", "Gemfile", "mix.exs",
        "Package.swift", "deno.json", "bun.lockb",
    ]
    lang_map = {
        "package.json": "JavaScript / TypeScript",
        "pyproject.toml": "Python", "requirements.txt": "Python", "setup.py": "Python",
        "Cargo.toml": "Rust", "go.mod": "Go",
        "build.gradle": "Java / Kotlin", "pom.xml": "Java",
        "CMakeLists.txt": "C / C++", "composer.json": "PHP",
        "Gemfile": "Ruby", "mix.exs": "Elixir",
        "Package.swift": "Swift", "deno.json": "TypeScript", "bun.lockb": "JavaScript / TypeScript",
    }

    for filename in checks:
        if (root / filename).exists():
            result["language"] = lang_map.get(filename, "Unknown")
            break

    # Fallback: check file extensions
    if result["language"] == "Unknown":
        ext_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".jsx": "React JSX", ".tsx": "React TSX",
            ".java": "Java", ".rs": "Rust", ".go": "Go",
            ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
            ".kt": "Kotlin", ".c": "C", ".cpp": "C++", ".h": "C/C++",
            ".cs": "C#", ".r": "R", ".scala": "Scala",
        }
        for ext, lang in ext_map.items():
            if ext in files:
                result["language"] = lang
                break

    # Detect framework
    framework_checks = [
        ("package.json", [
            ("react", "React"), ("vue", "Vue.js"), ("angular", "Angular"),
            ("next", "Next.js"), ("nuxt", "Nuxt.js"), ("svelte", "Svelte"),
            ("express", "Express.js"), ("django", "Django"),
            ("flask", "Flask"), ("fastapi", "FastAPI"),
            ("remix", "Remix"), ("gatsby", "Gatsby"),
            ("electron", "Electron"), ("expo", "Expo"),
        ]),
        ("pyproject.toml", [
            ("django", "Django"), ("flask", "Flask"), ("fastapi", "FastAPI"),
            ("tornado", "Tornado"), ("aiohttp", "aiohttp"),
        ]),
        ("requirements.txt", [
            ("django", "Django"), ("flask", "Flask"), ("fastapi", "FastAPI"),
        ]),
        ("Cargo.toml", [
            ("actix", "Actix-web"), ("rocket", "Rocket"), ("axum", "Axum"),
            ("warp", "Warp"), ("yew", "Yew"),
        ]),
        ("go.mod", [
            ("gin", "Gin"), ("echo", "Echo"), ("fiber", "Fiber"),
            ("chi", "Chi"), ("mux", "Gorilla Mux"),
        ]),
    ]
    for filename, fw_checks in framework_checks:
        filepath = root / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8", errors="replace")
            for fw_key, fw_name in fw_checks:
                if fw_key in content.lower():
                    result["framework"] = fw_name
                    break
            break

    # Check for version files
    for vfile in ["VERSION", ".version", "version.txt", "version.py", "version.rb"]:
        vpath = root / vfile
        if vpath.exists():
            result["version"] = vpath.read_text(encoding="utf-8", errors="replace").strip()[:30]
            break

    return result


def _detect_dependencies(root: Path, include_dev: bool = False) -> dict[str, Any]:
    """Detect package manager and list dependencies."""
    result: dict[str, Any] = {"manager": "None detected", "runtime_deps": [], "dev_deps": []}

    # Check by config file existence
    if (root / "package.json").exists():
        result["manager"] = _detect_js_manager(root)
        try:
            import json as _json
            pkg = _json.loads((root / "package.json").read_text(encoding="utf-8"))
            result["runtime_deps"] = list(pkg.get("dependencies", {}).keys())[:20]
            if include_dev:
                result["dev_deps"] = list(pkg.get("devDependencies", {}).keys())[:15]
            if pkg.get("engines", {}).get("node"):
                result["runtimes"] = f"Node {pkg['engines']['node']}"
        except Exception:
            pass

    elif (root / "pyproject.toml").exists():
        result["manager"] = "pip / poetry / uv"
        content = (root / "pyproject.toml").read_text(encoding="utf-8")
        match = re.findall(r'^([a-zA-Z0-9_.-]+)\s*[=~>]', content, re.MULTILINE)
        if match:
            result["runtime_deps"] = match[:20]
        # Check for Python version
        py_ver = re.search(r'requires-python\s*=\s*"[^"]*(\d+\.\d+)"', content)
        if py_ver:
            result["runtimes"] = f"Python {py_ver.group(1)}+"

    elif (root / "requirements.txt").exists():
        result["manager"] = "pip"
        deps = []
        for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith(("#", "-", "--")):
                deps.append(re.split(r"[=~<>!]", line)[0].strip())
        result["runtime_deps"] = deps[:20]

    elif (root / "Cargo.toml").exists():
        result["manager"] = "cargo"
        content = (root / "Cargo.toml").read_text(encoding="utf-8")
        match = re.findall(r'^([a-zA-Z0-9_-]+)\s*=', content, re.MULTILINE)
        if match:
            result["runtime_deps"] = [m for m in match if m.lower() not in ("edition", "name", "version")][:15]
        # Check for edition
        ed = re.search(r'edition\s*=\s*"(\d+)"', content)
        if ed:
            result["runtimes"] = f"Rust edition {ed.group(1)}"

    elif (root / "go.mod").exists():
        result["manager"] = "go mod"
        content = (root / "go.mod").read_text(encoding="utf-8")
        deps = re.findall(r'^\s+([a-zA-Z0-9./-]+)\s+v', content, re.MULTILINE)
        result["runtime_deps"] = deps[:15]
        go_ver = re.search(r'^go\s+(\d+\.\d+)', content, re.MULTILINE)
        if go_ver:
            result["runtimes"] = f"Go {go_ver.group(1)}"

    elif (root / "Gemfile").exists():
        result["manager"] = "bundler"
        deps = re.findall(r"^\s*gem\s+['\"]([^'\"]+)['\"]", (root / "Gemfile").read_text(encoding="utf-8"), re.MULTILINE)
        result["runtime_deps"] = deps[:15]

    elif (root / "composer.json").exists():
        result["manager"] = "composer"
        try:
            import json as _json
            comp = _json.loads((root / "composer.json").read_text(encoding="utf-8"))
            result["runtime_deps"] = list(comp.get("require", {}).keys())[:15]
            if include_dev:
                result["dev_deps"] = list(comp.get("require-dev", {}).keys())[:10]
        except Exception:
            pass

    elif (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        result["manager"] = "gradle"

    elif (root / "pom.xml").exists():
        result["manager"] = "maven"

    return result


def _detect_js_manager(root: Path) -> str:
    """Detect which JS package manager is used."""
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists() or (root / ".yarnrc.yml").exists():
        return "yarn"
    if (root / "bun.lockb").exists():
        return "bun"
    if (root / "package-lock.json").exists():
        return "npm"
    return "npm (no lockfile detected)"


def _analyze_structure(root: Path) -> dict[str, Any]:
    """Analyze project directory structure."""
    dirs = sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith("."))
    files = sorted(f.name for f in root.iterdir() if f.is_file() and not f.name.startswith("."))
    key_configs = [f.name for f in root.iterdir() if f.is_file() and f.suffix in
                   (".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".env.example")]

    # Count files by extension
    ext_count: dict[str, int] = {}
    total_files = 0
    for f in root.rglob("*"):
        if f.is_file() and not f.name.startswith(".") and ".git" not in f.parts:
            total_files += 1
            ext = f.suffix or "(no ext)"
            ext_count[ext] = ext_count.get(ext, 0) + 1

    top_exts = sorted(ext_count.items(), key=lambda x: -x[1])[:8]

    return {
        "top_dirs": dirs[:15],
        "key_files": files[:10] + key_configs[:5],
        "file_types": [f"{ext} ({count})" for ext, count in top_exts],
        "extensions": dict(top_exts),
        "file_count": total_files,
    }


def _find_entry_points(root: Path, language: str) -> list[str]:
    """Find likely entry points for the project."""
    entries = []

    # Common entry point files
    entry_checks = [
        "index.js", "index.ts", "index.jsx", "index.tsx",
        "app.js", "app.ts", "server.js", "server.ts", "main.py", "app.py",
        "wsgi.py", "manage.py", "cli.py", "main.rs", "main.go",
        "index.html", "src/index.js", "src/index.ts", "src/main.js", "src/main.ts",
        "lib/main.dart", "main.dart",
    ]

    for entry in entry_checks:
        ep = root / entry if isinstance(entry, Path) else root / str(entry).replace("/", os.sep)
        if ep.exists():
            entries.append(str(ep.relative_to(root)))

    # Check package.json "main" and "bin" fields
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            import json as _json
            pkg = _json.loads(pkg_json.read_text(encoding="utf-8"))
            for key in ("main", "module", "bin", "start"):
                if key in pkg:
                    val = pkg[key]
                    if isinstance(val, str):
                        entries.append(f"package.json → {key}: {val}")
                    elif isinstance(val, dict):
                        for k, v in val.items():
                            entries.append(f"package.json → {key}.{k}: {v}")
        except Exception:
            pass

    # Check pyproject.toml scripts
    pyproj = root / "pyproject.toml"
    if pyproj.exists():
        content = pyproj.read_text(encoding="utf-8")
        scripts = re.findall(r'^([a-zA-Z0-9_-]+)\s*=\s*"([^"]+)"', content, re.MULTILINE)
        for name, cmd in scripts[:3]:
            entries.append(f"pyproject.toml → script: {name} = {cmd}")

    return entries


def _detect_test_patterns(root: Path) -> dict[str, Any]:
    """Detect testing framework and find test files."""
    result: dict[str, Any] = {"framework": "Unknown", "count": 0, "command": ""}

    test_files = list(root.rglob("test_*.py")) + list(root.rglob("*_test.py")) + \
                 list(root.rglob("*_test.go")) + list(root.rglob("*_test.rs")) + \
                 list(root.rglob("*.test.js")) + list(root.rglob("*.test.ts")) + \
                 list(root.rglob("*.test.jsx")) + list(root.rglob("*.test.tsx")) + \
                 list(root.rglob("*.spec.js")) + list(root.rglob("*.spec.ts")) + \
                 list(root.rglob("__tests__/**/*")) + list(root.rglob("spec/**/*"))

    # Filter out node_modules, .venv, target
    test_files = [f for f in test_files if not any(
        ignore in f.parts for ignore in ("node_modules", ".venv", "target", "__pycache__", ".git")
    )]
    result["count"] = len(test_files)

    # Detect framework
    test_framework_checks = [
        ("pyproject.toml", [("pytest", "pytest"), ("unittest", "unittest")]),
        ("package.json", [("jest", "Jest"), ("vitest", "Vitest"), ("mocha", "Mocha"),
                          ("ava", "AVA"), ("tape", "Tape"), ("cypress", "Cypress"),
                          ("playwright", "Playwright")]),
        ("Cargo.toml", [("", "built-in #[test]")]),
    ]
    for filename, checks in test_framework_checks:
        filepath = root / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8", errors="replace").lower()
            for keyword, fw_name in checks:
                if not keyword or keyword in content:
                    result["framework"] = fw_name
                    break
            break

    # Detect test command
    command_checks = {
        "package.json": ["npm test", "yarn test", "pnpm test"],
        "Makefile": ["make test"],
        "pyproject.toml": ["pytest"],
        "Cargo.toml": ["cargo test"],
        "go.mod": ["go test ./..."],
    }
    for filename, cmds in command_checks.items():
        if (root / filename).exists():
            result["command"] = cmds[0]
            break

    # Fallback
    if result["framework"] == "Unknown" and result["count"] > 0:
        if test_files and test_files[0].suffix == ".py":
            result["framework"] = "pytest (assumed)"
            result["command"] = "pytest"
        elif test_files and test_files[0].suffix in (".js", ".ts"):
            result["framework"] = "Jest (assumed)"
            result["command"] = "npm test"

    return result


def _get_git_info(root: Path) -> dict[str, str]:
    """Get basic Git information."""
    info = {}
    git_dir = root / ".git"
    if not git_dir.exists():
        return info

    # Current branch
    head_file = git_dir / "HEAD"
    if head_file.exists():
        content = head_file.read_text(encoding="utf-8").strip()
        if content.startswith("ref: "):
            info["branch"] = content[5:].replace("refs/heads/", "")

    # Last commit message (from HEAD reflog or packed-refs)
    try:
        import subprocess
        r = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, timeout=5, cwd=str(root),
        )
        if r.returncode == 0 and r.stdout.strip():
            info["last_commit"] = r.stdout.strip()[:80]
    except Exception:
        pass

    return info


def _detect_conventions(root: Path, language: str) -> list[str]:
    """Detect coding conventions from existing files."""
    conventions = []

    # Check for formatter config files
    formatter_configs = [
        (".prettierrc", "Prettier"), (".prettierrc.json", "Prettier"),
        (".prettierrc.js", "Prettier"), (".prettierrc.yaml", "Prettier"),
        ("prettier.config.js", "Prettier"),
        (".eslintrc", "ESLint"), (".eslintrc.json", "ESLint"),
        (".eslintrc.js", "ESLint"),
        ("pyproject.toml", None),  # Check tool.ruff, tool.black
        (".ruff.toml", "Ruff"), ("ruff.toml", "Ruff"),
        (".rustfmt.toml", "rustfmt"), ("rustfmt.toml", "rustfmt"),
        (".golangci.yml", "golangci-lint"),
        (".editorconfig", "EditorConfig"),
        (".clang-format", "clang-format"),
    ]
    for config_file, tool_name in formatter_configs:
        if (root / config_file).exists():
            if tool_name:
                conventions.append(f"Formatter: {tool_name}")
            elif config_file == "pyproject.toml":
                content = (root / config_file).read_text(encoding="utf-8")
                if "[tool.black]" in content:
                    conventions.append("Formatter: Black")
                if "[tool.ruff]" in content:
                    conventions.append("Linter: Ruff")
                if "[tool.poetry]" in content:
                    conventions.append("Package manager: Poetry")
                if "[tool.uv]" in content:
                    conventions.append("Package manager: uv")

    # Detect import style from source files
    if language == "Python":
        py_files = list(root.rglob("*.py"))
        py_files = [f for f in py_files if "node_modules" not in str(f) and ".venv" not in str(f)]
        if py_files:
            sample = py_files[0].read_text(encoding="utf-8")
            if "from __future__ import annotations" in sample:
                conventions.append("Uses: from __future__ import annotations")
            # Detect type hints
            if ":" in sample and any(kw in sample for kw in ("def ", "class ")):
                if re.search(r"def \w+\([^)]*:\s*\w+", sample):
                    conventions.append("Type hints: Yes")
            # Detect async
            if "async def" in sample or "await " in sample:
                conventions.append("Async: Yes")

    # Detect TypeScript strict mode
    tsconfig = root / "tsconfig.json"
    if tsconfig.exists():
        content = tsconfig.read_text(encoding="utf-8")
        if '"strict": true' in content or '"strict":true' in content:
            conventions.append("TypeScript: strict mode")

    return conventions
