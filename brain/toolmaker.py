"""Tool Maker — AILIEN can create its own Python tools at runtime.

The LLM calls create_tool() with a tool name, description, params, and
Python source code. The ToolMaker validates, saves, and dynamically loads
the new tool so it's available immediately (no restart needed).
"""

import ast
import importlib.util
import inspect
import logging
import re
import sys
from pathlib import Path
from typing import Any

import tools

logger = logging.getLogger("agent")

# Directory for user/AI-generated tools
GENERATED_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools" / "generated"

_BLOCKED_PATTERNS = [
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bcompile\s*\(",
    r"\b__import__\s*\(",
    r"os\.system\s*\(",
    r"os\.popen\s*\(",
    r"os\.fork\s*\(",
    r"subprocess\.(Popen|call|check_output|run)\s*\(",
    r"shutil\.rmtree\s*\(",
]


def _ensure_generated_dir() -> Path:
    """Create the generated tools directory and __init__.py if missing."""
    GENERATED_TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    init_file = GENERATED_TOOLS_DIR / "__init__.py"
    if not init_file.exists():
        init_file.write_text(
            '# Generated tools — created dynamically by AILIEN\n'
            '# WARNING: This directory contains AI-generated code.\n'
            '"""Dynamically generated tools."""\n'
        )
    return GENERATED_TOOLS_DIR


def load_generated_tools() -> list[str]:
    """Load all generated tool modules from the generated directory.

    Returns a list of tool names that were registered.
    """
    _ensure_generated_dir()
    loaded = []
    for entry in sorted(GENERATED_TOOLS_DIR.iterdir()):
        if entry.name.startswith("_") or entry.suffix != ".py":
            continue
        if entry.name == "__init__.py":
            continue
        try:
            _load_module_from_path(entry)
            loaded.append(entry.stem)
            logger.info("Loaded generated tool module: %s", entry.name)
        except Exception as exc:
            logger.warning("Failed to load generated tool %s: %s", entry.name, exc)
    return loaded


def _load_module_from_path(filepath: Path) -> object:
    """Dynamically load a Python module from a file path using importlib.

    When the module is loaded, any @tool decorators in it will automatically
    register the functions in tools.TOOLS and tools._TOOL_FUNCTIONS.
    """
    module_name = f"tools.generated.{filepath.stem}"
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {filepath}")
    module = importlib.util.module_from_spec(spec)
    # Add to sys.modules so imports work
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def validate_tool_code(source: str) -> tuple[bool, str]:
    """Validate generated tool source code.

    Returns (is_valid, error_message).
    Checks:
    - Python syntax
    - Uses @tool decorator from tools
    - No dangerous imports/patterns
    - Defines at least one function
    """
    # Check syntax
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    # Check for dangerous patterns via regex on source
    for pattern in _BLOCKED_PATTERNS:
        if re.search(pattern, source):
            return False, f"Blocked dangerous pattern: {pattern}"

    # Walk the AST to check for dangerous imports and structure
    has_tool_decorator = False
    has_function_def = False
    has_tool_import = False

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tools":
                    has_tool_import = True
                # Block dangerous modules at top level
                if alias.name in ("os", "subprocess", "shutil", "ctypes", "pickle", "socket"):
                    return False, f"Blocked import: {alias.name} (use pathlib, requests, or specific functions instead)"

        if isinstance(node, ast.ImportFrom):
            if node.module == "tools":
                has_tool_import = True
            # Block dangerous imports from specific modules
            blocked_imports_from = {
                "os": ["system", "popen", "fork", "execv"],
                "subprocess": ["Popen", "call", "check_output", "run"],
                "shutil": ["rmtree", "chown"],
            }
            if node.module in blocked_imports_from:
                for alias in node.names:
                    if alias.name in blocked_imports_from[node.module]:
                        return False, f"Blocked import: from {node.module} import {alias.name}"

        # Check for @tool decorator
        if isinstance(node, ast.FunctionDef):
            has_function_def = True
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    if getattr(decorator.func, "id", None) == "tool":
                        has_tool_decorator = True
                elif isinstance(decorator, ast.Name) and decorator.id == "tool":
                    has_tool_decorator = True
                elif isinstance(decorator, ast.Attribute) and decorator.attr == "tool":
                    has_tool_decorator = True

    if not has_tool_import:
        return False, "Generated tool must import from tools (e.g., 'from tools import tool')"

    if not has_function_def:
        return False, "No function defined in the generated code"

    if not has_tool_decorator:
        return False, "No @tool-decorated function found. Use '@tool(name=..., description=..., params=..., required=[...])'"

    return True, "OK"


def create_tool_module(
    name: str,
    description: str,
    params: dict[str, Any],
    required: list[str],
    source_code: str,
) -> str:
    """Create and register a new tool module.

    Steps:
    1. Validate the source code
    2. Wrap it in a proper module with imports if needed
    3. Save to tools/generated/<name>.py
    4. Dynamically load it

    Returns a result message.
    """
    _ensure_generated_dir()

    # Validate
    is_valid, error = validate_tool_code(source_code)
    if not is_valid:
        return f"Cannot create tool: {error}"

    # The source code should contain the full module content including imports
    # and @tool decorator. We validate it's self-contained.
    filepath = GENERATED_TOOLS_DIR / f"{name}.py"

    if filepath.exists():
        return f"Tool '{name}' already exists in tools/generated/. Use a different name or remove it first."

    # Check for name collision with built-in tools
    if name in tools.list_tools():
        return f"Tool '{name}' conflicts with an existing built-in tool. Choose a different name."

    # Write the source code
    try:
        filepath.write_text(source_code, encoding="utf-8")
    except Exception as e:
        return f"Failed to write tool file: {e}"

    # Dynamically load it
    try:
        _load_module_from_path(filepath)
        logger.info("Created and registered new tool: %s", name)
        return f"✅ Tool '{name}' created and registered successfully!\n\nDescription: {description}\nFile: tools/generated/{name}.py\n\nAvailable for immediate use."
    except Exception as e:
        # Clean up the file if loading failed
        filepath.unlink(missing_ok=True)
        return f"Failed to load the new tool: {e}"


def list_generated_tools() -> list[str]:
    """List all tool names that were generated (not built-in)."""
    _ensure_generated_dir()
    tools_list = []
    for entry in sorted(GENERATED_TOOLS_DIR.iterdir()):
        if entry.name.startswith("_") or entry.suffix != ".py":
            continue
        if entry.name == "__init__.py":
            continue
        tools_list.append(entry.stem)
    return tools_list


def remove_generated_tool(name: str) -> str:
    """Remove a generated tool by name."""
    _ensure_generated_dir()
    filepath = GENERATED_TOOLS_DIR / f"{name}.py"

    if not filepath.exists():
        return f"Generated tool '{name}' not found."

    # Remove from registry if loaded
    tool_keys = list(tools._TOOL_FUNCTIONS.keys())
    for key in tool_keys:
        if key == name or key.startswith(f"{name}_"):
            del tools._TOOL_FUNCTIONS[key]
            # Also remove from the schemas list
            tools.TOOLS[:] = [t for t in tools.TOOLS
                             if t.get("function", {}).get("name") != key]

    filepath.unlink()
    logger.info("Removed generated tool: %s", name)
    return f"Removed tool '{name}'."
