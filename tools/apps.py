"""Application and window control tools."""
import shlex
import subprocess
from typing import Any

import psutil

from tools import tool


@tool(
    name="launch_app",
    description="Launch an application by name or command.",
    params={
        "command": {"type": "string", "description": "Command to run, e.g. 'firefox', 'code', 'gedit'"},
        "wait": {"type": "boolean", "description": "Whether to wait for the app to start (default false)", "default": False},
    },
    required=["command"],
)
def launch_app(command: str, wait: bool = False) -> str:
    try:
        args = shlex.split(command)
        if wait:
            subprocess.Popen(args).wait()
        else:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Launched: {command}"
    except Exception as e:
        return f"Failed to launch {command}: {e}"


@tool(
    name="list_running_apps",
    description="List currently running applications/processes.",
    params={
        "limit": {"type": "integer", "description": "Maximum number of processes to return (default 30)", "default": 30},
    },
    required=[],
)
def list_running_apps(limit: int = 30) -> str:
    procs = []
    for p in psutil.process_iter(["pid", "name", "username"]):
        try:
            info = p.info
            procs.append(f"{info['pid']:>6}  {info['name']}  ({info['username']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return "\n".join(procs[:limit])


@tool(
    name="kill_process",
    description="Kill a process by PID or name.",
    params={
        "pid": {"type": "integer", "description": "Process ID to kill"},
        "name": {"type": "string", "description": "Process name to kill (kills all matching)"},
    },
    required=[],
)
def kill_process(pid: int | None = None, name: str | None = None) -> str:
    killed = []
    if pid:
        try:
            p = psutil.Process(pid)
            p.terminate()
            killed.append(f"PID {pid} ({p.name()})")
        except Exception as e:
            return f"Failed to kill PID {pid}: {e}"
    if name:
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if p.info["name"].lower() == name.lower():
                    psutil.Process(p.info["pid"]).terminate()
                    killed.append(f"PID {p.info['pid']} ({name})")
            except Exception:
                continue
    if not killed:
        return "No processes killed."
    return f"Killed: {', '.join(killed)}"


@tool(
    name="find_process",
    description="Search for a running process by name.",
    params={
        "name": {"type": "string", "description": "Process name to search for (partial match)"},
    },
    required=["name"],
)
def find_process(name: str) -> str:
    matches = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = p.info
            search = " ".join(info.get("cmdline") or []) + " " + (info.get("name") or "")
            if name.lower() in search.lower():
                matches.append(f"PID {info['pid']}: {info['name']} - {' '.join(info.get('cmdline') or [])}")
        except Exception:
            continue
    if not matches:
        return f"No processes found matching '{name}'."
    return "\n".join(matches[:20])
