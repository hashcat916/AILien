"""Safety guard to prevent dangerous PC actions."""
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import config


class SafetyGuard:
    """Checks commands and actions for safety issues."""

    @staticmethod
    def is_dangerous_shell(command: str) -> bool:
        """Check if a shell command is dangerous."""
        # Normalize: lowercase, collapse whitespace
        normalized = " ".join(command.lower().strip().split())
        for pattern in config.DANGEROUS_PATTERNS:
            pat_normalized = " ".join(pattern.lower().split())
            if pat_normalized in normalized:
                return True
        return False

    @staticmethod
    def requires_confirmation(tool_name: str, params: dict[str, Any]) -> bool:
        """Check if a tool call requires user confirmation."""
        if not config.AGENT_CONFIRM_DANGEROUS:
            return False

        if tool_name in ("run_shell", "shell"):
            command = params.get("command", "")
            cmd_lower = command.lower()
            for pattern in config.REQUIRES_CONFIRMATION:
                if pattern.lower() in cmd_lower:
                    return True
            # Check for rm/del with wildcards
            if re.search(r"\brm\b.*[*?]", cmd_lower):
                return True
            if re.search(r"\bdel\b.*[*?]", cmd_lower):
                return True
            # Check for sudo escalation
            if re.search(r"\bsudo\b", cmd_lower):
                return True
            # Check for eval / exec of arbitrary strings
            if re.search(r"\beval\b|\bexec\b", cmd_lower):
                return True

        if tool_name in ("delete_file", "remove_file", "unlink", "kill_process"):
            return True

        if tool_name in ("format_drive", "shutdown", "reboot"):
            return True

        # Browser: confirm navigation to non-HTTP(S) URLs
        if tool_name in ("open_url", "browser_navigate", "get_webpage_text"):
            url = params.get("url", "")
            parsed_url = urlparse(url)
            if parsed_url.scheme and parsed_url.scheme not in ("http", "https"):
                return True

        return False

    @staticmethod
    def block_dangerous_shell(command: str) -> str:
        """Block obviously dangerous shell commands."""
        normalized = " ".join(command.lower().strip().split())
        dangerous = [
            "rm -rf /", "mkfs", ":(){ :|:& };:", "> /dev/sda",
            "dd if=/dev/zero", "dd if=/dev/urandom",
        ]
        for d in dangerous:
            d_norm = " ".join(d.lower().split())
            if d_norm in normalized:
                raise ValueError(f"Dangerous command blocked: {command}")
        return command

    @staticmethod
    def is_safe_path(path: str, base_dir: Path | None = None) -> bool:
        """Check that a path does not traverse above base_dir."""
        try:
            p = Path(path).expanduser().resolve()
            if base_dir is not None:
                base = base_dir.expanduser().resolve()
                p.relative_to(base)
            return True
        except (ValueError, RuntimeError):
            return False
