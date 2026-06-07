"""Automation management tools — schedule tasks to run at intervals or specific times.

The actual scheduling engine lives in brain/automation.py. These tools provide
the LLM-facing interface to manage automations.
"""

from tools import tool

_engine = None


def set_engine(engine) -> None:
    """Set the global AutomationEngine reference (called by main.py during init)."""
    global _engine
    _engine = engine


def get_engine():
    """Get the current AutomationEngine instance."""
    return _engine


@tool(
    name="add_automation",
    description="Schedule a tool to run automatically at intervals or at a specific time daily/hourly.",
    params={
        "label": {
            "type": "string",
            "description": "A name for this automation, e.g. 'check weather every morning'",
        },
        "schedule_type": {
            "type": "string",
            "description": "Schedule type: 'interval' (every N seconds), 'daily' (at a specific time), or 'hourly' (at a specific minute)",
        },
        "tool_name": {
            "type": "string",
            "description": "The tool to call when the automation triggers (e.g. 'weather', 'media_play_pause', 'system_info')",
        },
        "tool_params": {
            "type": "string",
            "description": "JSON string of parameters to pass to the tool, e.g. '{\"city\": \"London\"}' or '{}'",
            "default": "{}",
        },
        "interval_seconds": {
            "type": "integer",
            "description": "For 'interval' schedule: seconds between runs (minimum 30)",
            "default": 0,
        },
        "daily_hour": {
            "type": "integer",
            "description": "For 'daily' schedule: hour (0-23)",
            "default": 0,
        },
        "daily_minute": {
            "type": "integer",
            "description": "For 'daily' schedule: minute (0-59)",
            "default": 0,
        },
        "hourly_minute": {
            "type": "integer",
            "description": "For 'hourly' schedule: minute past the hour (0-59)",
            "default": 0,
        },
    },
    required=["label", "schedule_type", "tool_name"],
)
def add_automation(
    label: str,
    schedule_type: str,
    tool_name: str,
    tool_params: str = "{}",
    interval_seconds: int = 0,
    daily_hour: int = 0,
    daily_minute: int = 0,
    hourly_minute: int = 0,
) -> str:
    import json
    try:
        params_dict = json.loads(tool_params) if isinstance(tool_params, str) else tool_params
    except json.JSONDecodeError:
        return f"Invalid tool_params JSON: '{tool_params}'. Use valid JSON like '{{\"city\": \"London\"}}'."

    eng = get_engine()
    if eng is None:
        return "Automation system is not available."

    return eng.add_automation(
        label=label,
        schedule_type=schedule_type,
        tool_name=tool_name,
        tool_params=params_dict,
        interval_seconds=interval_seconds,
        daily_hour=daily_hour,
        daily_minute=daily_minute,
        hourly_minute=hourly_minute,
    )


@tool(
    name="list_automations",
    description="List all scheduled automations with their status and schedule.",
    params={},
    required=[],
)
def list_automations() -> str:
    eng = get_engine()
    if eng is None:
        return "Automation system is not available."
    return eng.list_automations()


@tool(
    name="remove_automation",
    description="Remove an automation by its ID or label text.",
    params={
        "identifier": {
            "type": "string",
            "description": "The automation ID or part of its label to remove",
        },
    },
    required=["identifier"],
)
def remove_automation(identifier: str) -> str:
    eng = get_engine()
    if eng is None:
        return "Automation system is not available."
    return eng.remove_automation(identifier)


@tool(
    name="pause_automation",
    description="Pause a specific automation by ID or label. It won't run until resumed.",
    params={
        "identifier": {
            "type": "string",
            "description": "The automation ID or part of its label to pause",
        },
    },
    required=["identifier"],
)
def pause_automation(identifier: str) -> str:
    eng = get_engine()
    if eng is None:
        return "Automation system is not available."
    return eng.pause_automation(identifier)


@tool(
    name="resume_automation",
    description="Resume a paused automation by ID or label.",
    params={
        "identifier": {
            "type": "string",
            "description": "The automation ID or part of its label to resume",
        },
    },
    required=["identifier"],
)
def resume_automation(identifier: str) -> str:
    eng = get_engine()
    if eng is None:
        return "Automation system is not available."
    return eng.resume_automation(identifier)


@tool(
    name="pause_all_automations",
    description="Pause ALL automations at once. No scheduled tasks will run.",
    params={},
    required=[],
)
def pause_all_automations() -> str:
    eng = get_engine()
    if eng is None:
        return "Automation system is not available."
    return eng.pause_all()


@tool(
    name="resume_all_automations",
    description="Resume ALL automations at once.",
    params={},
    required=[],
)
def resume_all_automations() -> str:
    eng = get_engine()
    if eng is None:
        return "Automation system is not available."
    return eng.resume_all()
