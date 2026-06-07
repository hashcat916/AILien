"""PC control tools exposed to the LLM agent."""
from typing import Any, Callable

# Registry of all available tools
TOOLS: list[dict[str, Any]] = []
_TOOL_FUNCTIONS: dict[str, Callable[..., Any]] = {}


def tool(name: str, description: str, params: dict[str, Any], required: list[str] | None = None):
    """Decorator to register a tool with its JSON schema."""
    schema = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": params,
                "required": required or [],
            },
        },
    }
    def decorator(func: Callable[..., Any]):
        TOOLS.append(schema)
        _TOOL_FUNCTIONS[name] = func
        return func
    return decorator


def get_tool(name: str) -> Callable[..., Any]:
    """Get a tool function by name."""
    return _TOOL_FUNCTIONS[name]


def list_tools() -> list[str]:
    """List all registered tool names."""
    return list(_TOOL_FUNCTIONS.keys())


def load_generated() -> list[str]:
    """Load all generated tools from the tools/generated/ directory.

    Called once at startup so any previously created tools are available.
    Returns a list of module names that were loaded.
    """
    try:
        from brain.toolmaker import load_generated_tools
        return load_generated_tools()
    except Exception:
        return []
