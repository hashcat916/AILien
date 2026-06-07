"""File system control tools."""
import os
import subprocess
from pathlib import Path

from tools import tool


@tool(
    name="list_directory",
    description="List files and folders in a directory.",
    params={
        "path": {"type": "string", "description": "Directory path (default current directory)", "default": "."},
    },
    required=[],
)
def list_directory(path: str = ".") -> str:
    from safety.guard import SafetyGuard
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Path does not exist: {p}"
        if not SafetyGuard.is_safe_path(str(p)):
            return f"Access denied: path traversal detected in '{path}'"
        entries = []
        for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            kind = "DIR" if entry.is_dir() else "FILE"
            size = entry.stat().st_size if entry.is_file() else "-"
            entries.append(f"{kind:4}  {size:>10}  {entry.name}")
        if not entries:
            return f"Directory is empty: {p}"
        header = f"{'Type':4}  {'Size':>10}  Name\n{'-'*40}"
        return header + "\n" + "\n".join(entries[:50])
    except Exception as e:
        return f"Error listing directory: {e}"


@tool(
    name="read_file",
    description="Read the contents of a text file.",
    params={
        "path": {"type": "string", "description": "File path to read"},
        "max_lines": {"type": "integer", "description": "Maximum lines to read (default 200)", "default": 200},
    },
    required=["path"],
)
def read_file(path: str, max_lines: int = 200) -> str:
    from safety.guard import SafetyGuard
    try:
        p = Path(path).expanduser().resolve()
        if not SafetyGuard.is_safe_path(str(p)):
            return f"Access denied: path traversal detected in '{path}'"
        if not p.is_file():
            return f"Not a file or does not exist: {p}"
        # Block reading sensitive system files
        sensitive_prefixes = ["/etc/shadow", "/etc/passwd", "/proc", "/sys", "/dev"]
        for prefix in sensitive_prefixes:
            if str(p).startswith(prefix):
                return f"Access denied: cannot read sensitive system file '{p}'"
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"\n... ({max_lines} lines shown, file truncated)")
                    break
                lines.append(line.rstrip("\n"))
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading file: {e}"


@tool(
    name="find_file",
    description="Search for files by name pattern in a directory.",
    params={
        "pattern": {"type": "string", "description": "Filename pattern, e.g. '*.py', 'document.txt'"},
        "directory": {"type": "string", "description": "Directory to search in (default current)", "default": "."},
        "max_results": {"type": "integer", "description": "Max results to return (default 20)", "default": 20},
    },
    required=["pattern"],
)
def find_file(pattern: str, directory: str = ".", max_results: int = 20) -> str:
    try:
        p = Path(directory).expanduser().resolve()
        matches = list(p.rglob(pattern))
        if not matches:
            return f"No files found matching '{pattern}' in {p}"
        return "\n".join(str(m) for m in matches[:max_results])
    except Exception as e:
        return f"Error searching: {e}"


@tool(
    name="open_file",
    description="Open a file with the default application.",
    params={
        "path": {"type": "string", "description": "File path to open"},
    },
    required=["path"],
)
def open_file(path: str) -> str:
    from safety.guard import SafetyGuard
    try:
        p = Path(path).expanduser().resolve()
        if not SafetyGuard.is_safe_path(str(p)):
            return f"Access denied: path traversal detected in '{path}'"
        if not p.exists():
            return f"File does not exist: {p}"
        if os.name == "nt":
            os.startfile(p)
        else:
            subprocess.Popen(["xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened: {p}"
    except Exception as e:
        return f"Error opening file: {e}"
