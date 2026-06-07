"""Shell command execution tools."""
import subprocess
import time

from tools import tool


@tool(
    name="run_shell",
    description="Run a shell command and return the output. Use this for any command-line operation.",
    params={
        "command": {"type": "string", "description": "The shell command to execute"},
        "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)", "default": 30},
        "cwd": {"type": "string", "description": "Working directory for the command (optional)"},
    },
    required=["command"],
)
def run_shell(command: str, timeout: int = 30, cwd: str | None = None) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or None,
        )
        output = result.stdout.strip()
        if result.stderr.strip():
            output += "\n[stderr] " + result.stderr.strip()
        if result.returncode != 0:
            output += f"\n[exit code {result.returncode}]"
        # Truncate very long output
        lines = output.splitlines()
        if len(lines) > 100:
            output = "\n".join(lines[:100]) + f"\n... ({len(lines) - 100} more lines)"
        return output
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error running command: {e}"
