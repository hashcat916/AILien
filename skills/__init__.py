"""Skill/plugin system for AILIEN.

Skills are pluggable modules that can extend the agent with new tools and
capabilities. Each skill module lives in the ``skills/`` directory and exports
a ``Skill`` subclass.

To create a skill::

    # skills/my_skill.py
    from skills import Skill, tool

    class WeatherSkill(Skill):
        name = "weather"
        description = "Gets the weather forecast"

        @tool
        def get_weather(self, city: str) -> str:
            return f"The weather in {city} is sunny, 72°F."
"""

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("agent")

# Registry of discovered skills
_skills: dict[str, "Skill"] = {}


class ToolDef:
    """Describes a tool registered by a skill."""

    def __init__(
        self,
        name: str,
        description: str,
        fn: Callable[..., Any],
        params: dict[str, Any] | None = None,
        required: list[str] | None = None,
    ):
        self.name = name
        self.description = description
        self.fn = fn
        self.params = params or {}
        self.required = required or []

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI tool-call schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.params,
                    "required": self.required,
                },
            },
        }


def tool(
    name: str | None = None,
    description: str = "",
    params: dict[str, Any] | None = None,
    required: list[str] | None = None,
) -> Callable:
    """Decorator to mark a method as a skill tool.

    Usage::

        class MySkill(Skill):
            @tool(description="Does something")
            def do_thing(self, arg: str) -> str:
                ...
    """
    def decorator(fn: Callable) -> Callable:
        fn._skill_tool_meta = {
            "name": name or fn.__name__,
            "description": description or fn.__doc__ or fn.__name__,
            "params": params or _infer_params(fn),
            "required": required or _infer_required(fn),
        }
        return fn
    return decorator


def _infer_params(fn: Callable) -> dict[str, Any]:
    """Crudely infer a JSON schema from function signature."""
    sig = inspect.signature(fn)
    params: dict[str, Any] = {}
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        param_type = "string"
        if param.annotation is not inspect.Parameter.empty:
            ann = str(param.annotation)
            if "int" in ann.lower():
                param_type = "integer"
            elif "float" in ann.lower() or "number" in ann.lower():
                param_type = "number"
            elif "bool" in ann.lower():
                param_type = "boolean"
        params[pname] = {"type": param_type, "description": pname.replace("_", " ")}
    return params


def _infer_required(fn: Callable) -> list[str]:
    """Infer required params (those without defaults)."""
    sig = inspect.signature(fn)
    required = []
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return required


class Skill:
    """Base class for all skills.

    Subclasses must set ``name`` and ``description``.
    Methods decorated with ``@tool`` are exposed to the agent.
    """

    name: str = ""
    description: str = ""

    def __init__(self) -> None:
        if not self.name:
            self.name = self.__class__.__name__.lower()
        self._discover_tools()

    def _discover_tools(self) -> None:
        """Scan for @tool-decorated methods and expose them."""
        self._tools: list[ToolDef] = []
        for name, method in inspect.getmembers(self, inspect.ismethod):
            meta = getattr(method, "_skill_tool_meta", None)
            if meta is not None:
                td = ToolDef(
                    name=f"skill_{self.name}_{meta['name']}",
                    description=meta["description"],
                    fn=method,
                    params=meta["params"],
                    required=meta["required"],
                )
                self._tools.append(td)
                logger.info("  Registered skill tool: %s", td.name)

    def get_tools(self) -> list[ToolDef]:
        return getattr(self, "_tools", [])

    def on_load(self) -> None:
        """Called when the skill is loaded. Override for setup."""
        pass

    def on_unload(self) -> None:
        """Called when the skill is unloaded. Override for cleanup."""
        pass


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def discover_skills(skills_dir: str | Path | None = None) -> dict[str, Skill]:
    """Scan the skills directory and return loaded Skill instances."""
    if skills_dir is None:
        # Check config for custom skills directory first
        try:
            import config
            if hasattr(config, 'SKILLS_DIR') and config.SKILLS_DIR:
                skills_dir = config.SKILLS_DIR
            else:
                skills_dir = Path(__file__).parent.resolve()
        except (ImportError, AttributeError):
            skills_dir = Path(__file__).parent.resolve()
    else:
        skills_dir = Path(skills_dir).resolve()

    if not skills_dir.is_dir():
        logger.warning("Skills directory not found: %s", skills_dir)
        return {}

    discovered: dict[str, Skill] = {}

    # Walk for Python files (non-__init__)
    for entry in sorted(skills_dir.iterdir()):
        if entry.name.startswith("_") or entry.suffix != ".py":
            continue
        module_name = entry.stem
        try:
            spec = importlib.util.spec_from_file_location(
                f"skills.{module_name}", entry
            )
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as exc:
            logger.warning("Failed to load skill module '%s': %s", module_name, exc)
            continue

        # Find Skill subclasses
        for obj_name in dir(mod):
            obj = getattr(mod, obj_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, Skill)
                and obj is not Skill
            ):
                try:
                    instance: Skill = obj()
                    instance.on_load()
                    discovered[instance.name] = instance
                    logger.info(
                        "Loaded skill: %s (%s) — %d tool(s)",
                        instance.name, instance.description, len(instance.get_tools()),
                    )
                except Exception as exc:
                    logger.warning("Failed to instantiate skill '%s': %s", obj_name, exc)

    return discovered


def load_all_skills() -> dict[str, Skill]:
    """Load all skills from the default skills directory."""
    skills_dir = Path(__file__).parent.resolve()
    discovered = discover_skills(skills_dir)
    _skills.update(discovered)
    return _skills


def get_skill_tools() -> list[ToolDef]:
    """Return all tool definitions from all loaded skills."""
    tools: list[ToolDef] = []
    for skill in _skills.values():
        tools.extend(skill.get_tools())
    return tools


def execute_skill_tool(name: str, **kwargs: Any) -> str:
    """Execute a skill tool by its full name (``skill_<skill>_<tool>``)."""
    for skill in _skills.values():
        for td in skill.get_tools():
            if td.name == name:
                try:
                    result = td.fn(**kwargs)
                    return str(result) if result is not None else "Done."
                except Exception as exc:
                    return f"Skill error: {exc}"
    return f"Skill tool not found: {name}"
