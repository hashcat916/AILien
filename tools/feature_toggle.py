"""Feature toggle tools — enable/disable background features at runtime.

Provides the LLM with tools to turn proactive monitoring, automation,
and other background features on and off without restarting.
"""

from tools import tool

# Global references set by main.py
_proactive_monitor = None
_automation_engine = None


def set_proactive_monitor(monitor) -> None:
    global _proactive_monitor
    _proactive_monitor = monitor


def set_automation_engine(engine) -> None:
    global _automation_engine
    _automation_engine = engine


@tool(
    name="toggle_proactive_monitoring",
    description="Turn proactive system monitoring on or off. When on, AILIEN alerts you about low battery, high CPU, etc.",
    params={
        "enabled": {
            "type": "boolean",
            "description": "True to enable monitoring, False to disable it",
        },
    },
    required=["enabled"],
)
def toggle_proactive_monitoring(enabled: bool) -> str:
    global _proactive_monitor
    if _proactive_monitor is None:
        return "Proactive monitoring is not available."
    
    try:
        if enabled:
            _proactive_monitor.start()
            return "Proactive monitoring enabled. I'll alert you about low battery, high CPU, and other issues."
        else:
            _proactive_monitor.stop()
            return "Proactive monitoring disabled. I won't send system alerts."
    except Exception as e:
        return f"Failed to toggle monitoring: {e}"


@tool(
    name="toggle_automation",
    description="Pause or resume all scheduled automations at once.",
    params={
        "paused": {
            "type": "boolean",
            "description": "True to pause all automations, False to resume them",
        },
    },
    required=["paused"],
)
def toggle_automation(paused: bool) -> str:
    global _automation_engine
    if _automation_engine is None:
        return "Automation system is not available."
    
    try:
        _automation_engine.set_paused(paused)
        if paused:
            return "All automations paused. No scheduled tasks will run."
        else:
            return "All automations resumed. Scheduled tasks will run normally."
    except Exception as e:
        return f"Failed to toggle automation: {e}"


@tool(
    name="get_feature_status",
    description="Get the current status of background features: proactive monitoring, automation, reminders.",
    params={},
    required=[],
)
def get_feature_status() -> str:
    global _proactive_monitor, _automation_engine
    
    lines = ["Background feature status:"]
    
    # Proactive monitoring
    if _proactive_monitor is not None:
        running = getattr(_proactive_monitor, '_running', False)
        lines.append(f"  🔍 Proactive monitoring: {'ON' if running else 'OFF'}")
    else:
        lines.append("  🔍 Proactive monitoring: unavailable")
    
    # Automation engine
    if _automation_engine is not None:
        paused = _automation_engine.is_paused
        auto_count = len(getattr(_automation_engine, '_automations', []))
        lines.append(f"  🤖 Automation engine: {'PAUSED' if paused else 'RUNNING'} ({auto_count} automations)")
    else:
        lines.append("  🤖 Automation engine: unavailable")
    
    return "\n".join(lines)
