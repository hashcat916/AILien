"""Tool creation tools — AILIEN can create its own tools at runtime.

The LLM calls create_tool with:
  - name: the tool name
  - description: what it does
  - params: JSON schema for parameters
  - required: list of required param names
  - code: full Python source code with @tool decorator and imports
"""

import json
from typing import Any

from tools import tool


@tool(
    name="create_tool",
    description="Create a new custom tool at runtime. Provide the source code with a @tool decorator, and AILIEN will validate, save, and register it immediately. Use this to extend your capabilities. WARNING: The tool becomes available right away.",
    params={
        "name": {"type": "string", "description": "Short name for the tool (e.g. 'search_packages', 'get_news')"},
        "description": {"type": "string", "description": "Description of what the tool does"},
        "params": {"type": "string", "description": "JSON schema string for parameters, e.g. '{\"query\": {\"type\": \"string\", \"description\": \"The search query\"}}'"},
        "required": {"type": "string", "description": "JSON array string of required parameter names, e.g. '[\"query\"]'"},
        "code": {"type": "string", "description": "Full Python source code for the tool module. Must import @tool from tools and have at least one @tool-decorated function. Use pathlib for files, requests for HTTP, datetime for dates. DO NOT use os.system, subprocess, eval, exec, or __import__."},
    },
    required=["name", "description", "params", "required", "code"],
)
def create_tool(name: str, description: str, params: str, required: str, code: str) -> str:
    """Create and register a new tool dynamically."""
    try:
        params_dict = json.loads(params) if isinstance(params, str) else params
    except json.JSONDecodeError as e:
        return f"Invalid params JSON: {e}"

    try:
        required_list = json.loads(required) if isinstance(required, str) else required
    except json.JSONDecodeError as e:
        return f"Invalid required JSON: {e}"

    # Validate the params schema format
    if not isinstance(params_dict, dict):
        return "params must be a JSON object with parameter names as keys"

    from brain.toolmaker import create_tool_module
    return create_tool_module(name, description, params_dict, required_list, code)


@tool(
    name="list_created_tools",
    description="List all tools that have been created dynamically (custom/user-generated tools).",
    params={},
    required=[],
)
def list_created_tools() -> str:
    """List all generated/custom tools."""
    from brain.toolmaker import list_generated_tools
    tools_list = list_generated_tools()
    if not tools_list:
        return "No custom tools have been created yet. Use 'create_tool' to make one."
    return "Custom created tools:\n" + "\n".join(f"  • {t}" for t in tools_list)


@tool(
    name="remove_created_tool",
    description="Remove a previously created custom tool by name.",
    params={
        "name": {"type": "string", "description": "Name of the generated tool to remove"},
    },
    required=["name"],
)
def remove_created_tool(name: str) -> str:
    """Remove a generated tool by name."""
    from brain.toolmaker import remove_generated_tool
    return remove_generated_tool(name)
