"""Code tools — syntax checking, test running, project introspection."""
import ast
import subprocess
import sys
from pathlib import Path

import config

from tools import tool


@tool(
    name="check_python_syntax",
    description="Check a Python file for syntax errors without running it. Also reports code quality issues.",
    params={
        "filepath": {"type": "string", "description": "Path to the Python file to check (relative to project root or absolute)"},
    },
    required=["filepath"],
)
def check_python_syntax(filepath: str) -> str:
    """Parse a Python file with ast to check for syntax errors."""
    path = Path(filepath)
    if not path.is_absolute():
        path = config.PROJECT_DIR / path

    if not path.exists():
        return f"File not found: {path}"
    if path.suffix != ".py":
        return f"Not a Python file: {path}"

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError as e:
        return f"❌ Syntax error in {path.name}:\n  Line {e.lineno}: {e.msg}\n  Text: {e.text.strip() if e.text else ''}"
    except Exception as e:
        return f"❌ Error reading {path.name}: {e}"

    # Check for some code quality issues
    issues = []
    for node in ast.walk(tree):
        # Check for bare except
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append("  ⚠️  Bare 'except:' clause — catches all exceptions")
        # Check for TODO comments
    for i, line in enumerate(source.split("\n"), 1):
        stripped = line.strip().upper()
        if "TODO" in stripped or "FIXME" in stripped or "HACK" in stripped:
            issues.append(f"  📝 Line {i}: {line.strip()}")

    result = f"✅ {path.name} — syntax OK"
    if issues:
        result += "\n" + "\n".join(issues)
    return result


@tool(
    name="run_project_tests",
    description="Run the project's unit tests using pytest. Returns the test results.",
    params={
        "test_path": {"type": "string", "description": "Specific test file or directory to run (default: all tests)", "default": ""},
        "verbose": {"type": "boolean", "description": "If true, shows detailed test output", "default": False},
    },
    required=[],
)
def run_project_tests(test_path: str = "", verbose: bool = False) -> str:
    """Run pytest on the project's test suite."""
    project_dir = config.PROJECT_DIR
    python = project_dir / ".venv" / "bin" / "python3"

    cmd = [str(python), "-m", "pytest"]
    if verbose:
        cmd.append("-v")
    cmd.append("--tb=short")
    cmd.append("-q")

    if test_path:
        tp = Path(test_path)
        if not tp.is_absolute():
            tp = project_dir / tp
        cmd.append(str(tp))
    else:
        cmd.append(str(project_dir / "tests"))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=120,
            cwd=project_dir,
        )
        output = result.stdout + result.stderr
        # Limit to 2000 chars
        if len(output) > 2000:
            output = output[:2000] + "\n... (truncated)"
        return output.strip() or "Tests completed with no output."
    except subprocess.TimeoutExpired:
        return "Tests timed out after 120 seconds."
    except Exception as e:
        return f"Failed to run tests: {e}"


@tool(
    name="format_python",
    description="Format a Python file using Black (auto-formatter) and return the result.",
    params={
        "filepath": {"type": "string", "description": "Path to the Python file to format"},
        "check_only": {"type": "boolean", "description": "If true, only check if file is already formatted (don't modify)", "default": False},
    },
    required=["filepath"],
)
def format_python(filepath: str, check_only: bool = False) -> str:
    """Run Black on a Python file."""
    path = Path(filepath)
    if not path.is_absolute():
        path = config.PROJECT_DIR / path

    if not path.exists():
        return f"File not found: {path}"

    python = config.PROJECT_DIR / ".venv" / "bin" / "python3"
    try:
        cmd = [str(python), "-m", "black"]
        if check_only:
            cmd.append("--check")
        cmd.append("--quiet")
        cmd.append(str(path))

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return f"✅ {path.name} is properly formatted."
        elif result.returncode == 1 and not check_only:
            return f"✅ {path.name} has been reformatted."
        elif result.returncode == 1 and check_only:
            return f"❌ {path.name} needs formatting.\n{result.stdout.strip()}"
        return f"Black returned code {result.returncode}:\n{result.stderr.strip()[:500]}"
    except Exception as e:
        return f"Failed to format: {e}"


@tool(
    name="self_verify",
    description="After making changes, call this to verify everything is correct: checks syntax of modified files, runs tests, and reports issues. Use this to self-correct.",
    params={
        "files": {"type": "string", "description": "Comma-separated list of file paths that were modified (optional — if empty, checks all .py files in the project)", "default": ""},
        "run_tests": {"type": "boolean", "description": "If true, also runs the project's test suite (default true)", "default": True},
    },
    required=[],
)
def self_verify(files: str = "", run_tests: bool = True) -> str:
    """Verify modified files: syntax check + tests. Helps AILIEN self-correct."""
    results = []
    errors = []

    # Determine which files to check
    if files.strip():
        file_list = [f.strip() for f in files.split(",") if f.strip()]
    else:
        # Default: check all .py files in the project
        file_list = [str(p.relative_to(config.PROJECT_DIR))
                     for p in config.PROJECT_DIR.rglob("*.py")
                     if ".venv" not in str(p) and "__pycache__" not in str(p)]

    # Check syntax of each file
    for f in file_list:
        try:
            path = Path(f)
            if not path.is_absolute():
                path = config.PROJECT_DIR / path
            if not path.exists():
                results.append(f"⚠️  {f} — not found, skipped")
                continue
            if path.suffix != ".py":
                results.append(f"⚠️  {f} — not a Python file, skipped")
                continue

            source = path.read_text(encoding="utf-8")
            ast.parse(source)
            results.append(f"✅ {f} — syntax OK")
        except SyntaxError as e:
            msg = f"❌ {f} — syntax error line {e.lineno}: {e.msg}"
            results.append(msg)
            errors.append(msg)
        except Exception as e:
            results.append(f"❌ {f} — error: {e}")
            errors.append(f"❌ {f} — error: {e}")

    # Run tests
    test_result = ""
    if run_tests:
        try:
            python = config.PROJECT_DIR / ".venv" / "bin" / "python3"
            result = subprocess.run(
                [str(python), "-m", "pytest", "--tb=short", "-q", str(config.PROJECT_DIR / "tests")],
                capture_output=True, text=True, timeout=120,
                cwd=config.PROJECT_DIR,
            )
            output = (result.stdout + result.stderr).strip()
            if result.returncode == 0:
                test_result = "✅ All tests passed."
            else:
                # Truncate long output
                if len(output) > 1000:
                    output = output[:1000] + "\n... (truncated)"
                test_result = f"❌ Tests failed:\n{output}"
                errors.append(test_result)
        except subprocess.TimeoutExpired:
            test_result = "⏱️  Tests timed out after 120s."
        except Exception as e:
            test_result = f"❌ Could not run tests: {e}"
            errors.append(test_result)

    # Build summary
    summary = "=== Self-Verification Results ===\n\n"
    summary += "\n".join(results) + "\n"
    if test_result:
        summary += f"\n{test_result}\n"

    if errors:
        summary += f"\n❌ {len(errors)} issue(s) found — review and fix before continuing."
    else:
        summary += "\n✅ All checks passed — changes look good."

    return summary
