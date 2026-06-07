"""Reasoning tools — AILIEN can think, plan, review, run commands, and suggest like a full agent.

Provides:
  - think()           — structured deep reasoning before acting
  - create_plan()     — todo-list tracking for multi-step tasks
  - list_plans()      — see active plans
  - complete_step()   — mark a plan step done
  - self_review()     — code review (calls self_verify + code quality analysis)
  - run_command()     — lightweight basher for safe verification commands
  - suggest_next_steps() — suggest followups after completing work
"""

import ast
import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import config
from tools import tool

logger = logging.getLogger("agent")

_PLANS_DIR = config.CACHE_DIR / "plans"
_PLANS_DIR.mkdir(parents=True, exist_ok=True)


# ===================================================================
# SAFE COMMANDS — commands run_command allows without confirmation
# ===================================================================

# Commands/tools that are safe for lightweight verification
_SAFE_COMMAND_PREFIXES = [
    "python3 -c", "python -c",
    "pip list", "pip show", "pip install",
    "cat ", "head ", "tail ", "wc ", "ls ", "find ",
    "python3 -m pytest", "python -m pytest",
    "python3 -m black", "python -m black",
    "python3 -m flake8", "python -m flake8",
    "which ", "type ",
    "echo ",
    "cd ", "pwd",
    "git status", "git diff", "git log", "git branch",
    "npm ls", "cargo check", "go build",
]

# Commands that are NEVER allowed (destructive)
_BLOCKED_COMMANDS = [
    "rm -rf", "rm -r", "rm -f",
    "sudo ", "chmod 777", "chown ",
    "dd ", "mkfs", "fdisk", "format",
    ":(){ :|:& };:",  # fork bomb
    "> ", "| sh", "| bash",
    "wget ", "curl ",
]


def _is_command_safe(command: str) -> tuple[bool, str]:
    """Check if a command is safe to run without confirmation.

    Returns (safe, reason). If not safe, reason explains why.
    """
    lower = command.lower().strip()

    # Check blocked commands first
    for blocked in _BLOCKED_COMMANDS:
        if lower.startswith(blocked):
            return False, f"Command matches blocked pattern: '{blocked}'"

    # Check safe prefixes
    for prefix in _SAFE_COMMAND_PREFIXES:
        if lower.startswith(prefix):
            return True, ""

    # Allow any python3/python command that's clearly non-destructive
    if lower.startswith(("python3 ", "python ")):
        # Block anything with os.system, subprocess, eval, exec
        blocked_keywords = ["os.system", "subprocess", "eval(", "exec("]
        for kw in blocked_keywords:
            if kw in lower:
                return False, f"Python command contains blocked keyword: '{kw}'"
        return True, ""

    return False, "Command not in safe list. Use run_shell instead."


# ===================================================================
# 💭 THINK — structured deep reasoning
# ===================================================================

@tool(
    name="think",
    description="Step back and reason deeply about a problem before acting. Call this before complex multi-step tasks to organize your thoughts.",
    params={
        "problem": {"type": "string", "description": "What you need to think about — describe the problem or goal clearly"},
        "context": {"type": "string", "description": "Additional context: what files are involved, constraints, preferences, etc.", "default": ""},
    },
    required=["problem"],
)
def think(problem: str, context: str = "") -> str:
    """Return a structured thinking framework for the LLM to fill in."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ctx = f"\n   Context: {context}" if context else ""

    return (
        f"🧠 Structured Reasoning\n"
        f"   Problem: {problem}{ctx}\n"
        f"   Time: {now}\n\n"
        f"─── THINKING FRAMEWORK ──────────────────────────────\n"
        f"\n"
        f"1. ANALYSIS — What's being asked? What do I know?\n"
        f"   • Break down the request into clear parts\n"
        f"   • What files/tools/knowledge do I need?\n"
        f"   • What are the constraints or preferences?\n"
        f"\n"
        f"2. OPTIONS — What approaches could work?\n"
        f"   • Option A: ... (pros/cons)\n"
        f"   • Option B: ... (pros/cons)\n"
        f"\n"
        f"3. PLAN — What's the chosen approach?\n"
        f"   • Step 1: ...\n"
        f"   • Step 2: ...\n"
        f"   • Step 3: ...\n"
        f"\n"
        f"4. VERIFICATION — How will I know it works?\n"
        f"   • What tests or checks to run?\n"
        f"   • What could go wrong?\n"
        f"\n"
        f"─── Fill in your reasoning above ─────────────────────"
    )


# ===================================================================
# 📋 PLANS — todo tracking for multi-step tasks
# ===================================================================

def _plan_path(name: str) -> Path:
    """Get the file path for a plan (name is sanitized)."""
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', name.lower()).strip('_') or "plan"
    return _PLANS_DIR / f"{safe}.json"


def _load_plan(name: str) -> dict | None:
    """Load a plan by name (with fuzzy match fallback)."""
    path = _plan_path(name)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    for plan_file in sorted(_PLANS_DIR.glob("*.json")):
        try:
            data = json.loads(plan_file.read_text(encoding="utf-8"))
            stored = data.get("name", "").lower()
            if name.lower() in stored:
                return data
        except Exception:
            continue
    return None


def _save_plan(plan: dict) -> None:
    """Save a plan to disk."""
    path = _plan_path(plan["name"])
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


@tool(
    name="create_plan",
    description="Create a step-by-step plan/todo list for a multi-step task. Use this before starting complex work.",
    params={
        "name": {"type": "string", "description": "Short name for the plan (e.g. 'web_scraper', 'cli_overhaul')"},
        "steps": {"type": "string", "description": "Comma-separated list of steps. E.g. 'design API, implement fetch, add tests, run tests'"},
        "description": {"type": "string", "description": "Optional description of what this plan is for", "default": ""},
    },
    required=["name", "steps"],
)
def create_plan(name: str, steps: str, description: str = "") -> str:
    """Create a plan with todo steps."""
    step_list = [s.strip() for s in steps.split(",") if s.strip()]
    if not step_list:
        return "Need at least one step."

    plan = {
        "name": name,
        "description": description,
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "steps": [{"id": i + 1, "task": s, "completed": False} for i, s in enumerate(step_list)],
        "completed": False,
    }
    _save_plan(plan)

    lines = [f"📋 Plan: {name}"]
    if description:
        lines.append(f"   {description}")
    lines.append(f"   {len(step_list)} step(s):")
    for i, step in enumerate(step_list, 1):
        lines.append(f"     {i}. [ ] {step}")
    lines.append("")
    lines.append("Use complete_step(plan_name, step_number) to track progress.")
    return "\n".join(lines)


@tool(
    name="list_plans",
    description="List all active plans and their completion status.",
    params={},
    required=[],
)
def list_plans() -> str:
    """List all saved plans with their progress."""
    plans = sorted(_PLANS_DIR.glob("*.json"))
    if not plans:
        return "No plans yet. Use create_plan to start tracking a task."

    lines = ["📋 Active Plans:"]
    for p in plans:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            steps = data.get("steps", [])
            total = len(steps)
            done = sum(1 for s in steps if s.get("completed"))
            pct = int(done / total * 100) if total > 0 else 0
            status = "✅" if data.get("completed") else "🔄"
            desc = f" — {data['description']}" if data.get("description") else ""
            lines.append(f"\n  {status} {data['name']}{desc}")
            lines.append(f"     {done}/{total} steps completed ({pct}%)")
            for s in steps:
                if not s.get("completed"):
                    lines.append(f"     Next: {s['task']}")
                    break
        except Exception:
            lines.append(f"\n  ⚠️  {p.stem} (corrupted)")
    return "\n".join(lines)


@tool(
    name="complete_step",
    description="Mark a step as completed in a plan. Call this after finishing each step.",
    params={
        "plan_name": {"type": "string", "description": "Name of the plan (as given to create_plan)"},
        "step_number": {"type": "integer", "description": "Step number to mark complete (1-based)"},
        "notes": {"type": "string", "description": "Optional notes about what was done", "default": ""},
    },
    required=["plan_name", "step_number"],
)
def complete_step(plan_name: str, step_number: int, notes: str = "") -> str:
    """Mark a step as completed in a plan."""
    plan = _load_plan(plan_name)
    if plan is None:
        return f"No plan found matching '{plan_name}'. Use list_plans to see available plans."

    steps = plan.get("steps", [])
    if step_number < 1 or step_number > len(steps):
        return f"Step {step_number} out of range. Plan has {len(steps)} steps (1-{len(steps)})."

    step = steps[step_number - 1]
    step["completed"] = True
    step["completed_at"] = datetime.now().isoformat()
    if notes:
        step["notes"] = notes

    plan["updated"] = datetime.now().isoformat()
    plan["completed"] = all(s.get("completed") for s in steps)
    _save_plan(plan)

    total = len(steps)
    done = sum(1 for s in steps if s.get("completed"))
    remaining = total - done

    result = [f"✅ Step {step_number} completed: {step['task']}"]
    result.append(f"   Progress: {done}/{total} ({int(done/total*100)}%)")
    if remaining > 0:
        for s in steps:
            if not s.get("completed"):
                result.append(f"   Next up: {s['task']}")
                break
    else:
        result.append("\n🎉 All steps completed! Plan finished.")
    return "\n".join(result)


# ===================================================================
# 🔍 SELF-REVIEW — code review (calls self_verify + quality checks)
# ===================================================================

@tool(
    name="self_review",
    description="Review code changes after making edits. Checks syntax, runs tests, and provides structured feedback with improvement suggestions.",
    params={
        "files": {"type": "string", "description": "Comma-separated list of files that were changed (pass the actual filenames you modified)", "default": ""},
        "run_tests": {"type": "boolean", "description": "Run the project test suite as part of review", "default": True},
    },
    required=[],
)
def self_review(files: str = "", run_tests: bool = True) -> str:
    """Review changed files: delegates to self_verify, then adds quality analysis."""
    sections = []

    # 1. Run self_verify for syntax + tests
    from tools.code_tools import self_verify
    verify_result = self_verify(files=files, run_tests=run_tests)
    sections.append(verify_result)

    # 2. Code quality checks (on top of syntax check)
    quality_notes = []
    if files.strip():
        file_list = [f.strip() for f in files.split(",") if f.strip()]
    else:
        file_list = []

    for f in file_list:
        path = Path(f)
        if not path.is_absolute():
            path = config.PROJECT_DIR / path
        if not path.exists() or path.suffix != ".py":
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            notes = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    notes.append("   ⚠️  Bare except — catches all exceptions silently")
                if isinstance(node, ast.FunctionDef):
                    flines = (node.end_lineno or node.lineno) - node.lineno
                    if flines > 80:
                        notes.append(f"   📏 '{node.name}' is {flines} lines — consider splitting")
            for i, line in enumerate(source.split("\n"), 1):
                upper = line.strip().upper()
                if any(kw in upper for kw in ["TODO", "FIXME", "HACK", "XXX"]):
                    notes.append(f"   📝 L{i}: {line.strip()}")
            if notes:
                quality_notes.append(f"📄 {f} — {len(notes)} suggestion(s)")
                quality_notes.extend(notes)
        except Exception:
            pass

    if quality_notes:
        sections.append("\n🔍 Code Quality:")
        sections.extend(quality_notes)

    # 3. Summary suggestions
    sections.append("")
    if "❌" in sections[0]:
        sections.append("💡 Fix the syntax/test issues above before continuing.")
    elif quality_notes:
        sections.append("💡 Code works but could be cleaner. Consider the quality notes above.")
    else:
        sections.append("💡 Everything looks good.")
    return "\n".join(sections)


# ===================================================================
# 🏃 RUN COMMAND — lightweight basher for safe verification
# ===================================================================
# Lightweight command runner inspired by Buffy's basher agent.
# Allows safe verification commands without the heavy confirmation
# required by run_shell. Keeps AILIEN in a fast verify loop.

@tool(
    name="run_command",
    description="Run a safe verification command (like a basher agent). Ideal for checking syntax, running one-off Python tests, listing files, checking installed packages, and other lightweight verifications. For dangerous commands, use run_shell instead — it will prompt for confirmation.",
    params={
        "command": {"type": "string", "description": "Command to run. Safe commands: python3 -c, pip list, ls, cat, head, git status, pytest (limited), and similar non-destructive operations."},
        "what_to_check": {"type": "string", "description": "What you're trying to verify or learn from running this command (helps interpret output)", "default": ""},
    },
    required=["command"],
)
def run_command(command: str, what_to_check: str = "") -> str:
    """Run a safe verification command (lightweight basher)."""
    safe, reason = _is_command_safe(command)
    if not safe:
        return (
            f"⛔ Command blocked: {reason}\n\n"
            f"This command isn't in the safe list. If you need to run it, use run_shell instead "
            f"(it will ask the user for confirmation)."
        )

    try:
        import subprocess
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        if len(output) > 3000:
            output = output[:3000] + "\n... (truncated)"

        status = "✅" if result.returncode == 0 else "⚠️"
        cmd_preview = command[:80] + ("..." if len(command) > 80 else "")
        parts = [f"{status} Command: {cmd_preview}"]
        if what_to_check:
            parts.append(f"   Check: {what_to_check}")
        parts.append(f"   Exit code: {result.returncode}")
        if output.strip():
            parts.append("")
            parts.append(output.strip())
        return "\n".join(parts)

    except subprocess.TimeoutExpired:
        return f"⏱️  Command timed out after 30s: {command[:80]}"
    except Exception as e:
        return f"❌ Command failed: {e}"


# ===================================================================
# 💡 SUGGEST NEXT STEPS
# ===================================================================

@tool(
    name="suggest_next_steps",
    description="After completing a task, call this to suggest what the user might want to do next. Provides a framework for helpful followup ideas.",
    params={
        "context": {"type": "string", "description": "What was just completed or what the user is working on", "default": ""},
    },
    required=[],
)
def suggest_next_steps(context: str = "") -> str:
    """Return a template for suggesting followup actions."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ctx = f"\n   Context: {context}" if context else ""

    return (
        f"💡 Suggest Next Steps\n"
        f"   Time: {now}{ctx}\n\n"
        f"─── What to suggest ────────────────────────────────\n"
        f"\n"
        f"Now that this task is done, think about what would be useful next:\n"
        f"\n"
        f"• Testing — Add unit tests for the changes\n"
        f"• Refinement — Polish edge cases, error handling, docs\n"
        f"• Extension — Build on this with related features\n"
        f"• Cleanup — Remove unused code, consolidate files\n"
        f"• Integration — Wire this into other parts of the system\n"
        f"\n"
        f"Suggest 2-3 specific, actionable next steps to the user.\n"
        f"Make each suggestion clear and directly build on what was done.\n"
        f"───────────────────────────────────────────────────"
    )
