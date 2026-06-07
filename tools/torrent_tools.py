"""Torrent download tool — download via Transmission (transmission-remote)."""

import os
import shutil
import subprocess
import time
from pathlib import Path

from tools import tool

# ---------------------------------------------------------------------------
# Transmission setup
# ---------------------------------------------------------------------------
_TRANSMISSION_REMOTE: str | None = None
_TRANSMISSION_DAEMON: str | None = None
_TRANSMISSION_GTK: str | None = None


def _locate_transmission() -> tuple[str | None, str | None, str | None]:
    """Locate transmission binaries and ensure the daemon is running.

    Returns (transmission-remote path, transmission-daemon path, transmission-gtk path).
    """
    global _TRANSMISSION_REMOTE, _TRANSMISSION_DAEMON, _TRANSMISSION_GTK

    if _TRANSMISSION_REMOTE is not None:
        return _TRANSMISSION_REMOTE, _TRANSMISSION_DAEMON, _TRANSMISSION_GTK

    _TRANSMISSION_REMOTE = shutil.which("transmission-remote")
    _TRANSMISSION_DAEMON = shutil.which("transmission-daemon")
    _TRANSMISSION_GTK = shutil.which("transmission-gtk")

    return _TRANSMISSION_REMOTE, _TRANSMISSION_DAEMON, _TRANSMISSION_GTK


def _ensure_daemon_running() -> bool:
    """Make sure the Transmission daemon is running."""
    _, daemon_path, _ = _locate_transmission()

    if daemon_path is None:
        # Try to find and start it manually
        daemon_path = shutil.which("transmission-daemon")
        if daemon_path is None:
            return False

    # Check if it's already running
    try:
        result = subprocess.run(
            ["pgrep", "-x", "transmission-daemon"],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            return True  # Already running
    except FileNotFoundError:
        pass

    # Start the daemon
    try:
        subprocess.Popen(
            [daemon_path, "--no-messages"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)  # Give it a moment to start
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool(
    name="add_torrent",
    description="Download a torrent via Transmission. Accepts a magnet link or .torrent URL.",
    params={
        "uri": {
            "type": "string",
            "description": "Magnet link (magnet:?xt=...) or .torrent URL to download",
        },
        "download_dir": {
            "type": "string",
            "description": "Directory to save the downloaded files (default ~/Downloads)",
            "default": "",
        },
    },
    required=["uri"],
)
def add_torrent(uri: str, download_dir: str = "") -> str:
    """Add a torrent via Transmission's daemon (transmission-remote)."""
    remote_path, _, _ = _locate_transmission()

    if remote_path is None:
        # Offer to install it
        return (
            "transmission-remote is not installed. Install it with:\n"
            "  sudo apt install transmission-cli transmission-daemon\n"
            "Then try again."
        )

    if not uri.strip():
        return "Please provide a magnet link or torrent URL."

    # Ensure daemon is running
    if not _ensure_daemon_running():
        return "Could not start the Transmission daemon. Try running 'transmission-daemon' manually."

    # Build the command
    cmd = [remote_path]

    if download_dir:
        dl_path = Path(download_dir).expanduser().resolve()
        if dl_path.is_dir():
            cmd.extend(["--download-dir", str(dl_path)])

    cmd.extend(["--add", uri])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=30,
        )

        if result.returncode == 0:
            # Check if the torrent was added
            time.sleep(1)
            info = subprocess.run(
                [remote_path, "--list"],
                capture_output=True, text=True, timeout=10,
            )
            if "Sum" in info.stdout.strip() or "ID" in info.stdout.lower():
                return (
                    f"Torrent added to Transmission.\n"
                    f"Use 'torrent_status' to check progress.\n"
                    f"Downloads are saved to: {download_dir or '~/Downloads'}"
                )
            return f"Torrent added. Transmission response: {result.stdout.strip() or 'OK'}"
        else:
            return f"Failed to add torrent: {result.stderr.strip() or result.stdout.strip() or 'Unknown error'}"

    except subprocess.TimeoutExpired:
        return "Timed out adding torrent. The magnet link might be slow to resolve."
    except Exception as e:
        return f"Error adding torrent: {e}"


@tool(
    name="torrent_status",
    description="Show the status of all active and pending torrents in Transmission.",
    params={},
    required=[],
)
def torrent_status() -> str:
    """List all torrents and their progress."""
    remote_path, _, _ = _locate_transmission()
    if remote_path is None:
        return "transmission-remote is not installed."

    try:
        result = subprocess.run(
            [remote_path, "--list"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"Transmission torrents:\n{result.stdout.strip()}"
        else:
            return "No active torrents in Transmission."
    except Exception as e:
        return f"Could not get torrent status: {e}"


@tool(
    name="torrent_pause",
    description="Pause a torrent in Transmission by its ID number.",
    params={
        "torrent_id": {
            "type": "integer",
            "description": "Torrent ID number (use torrent_status to find IDs)",
        },
    },
    required=["torrent_id"],
)
def torrent_pause(torrent_id: int) -> str:
    """Pause a specific torrent."""
    remote_path, _, _ = _locate_transmission()
    if remote_path is None:
        return "transmission-remote is not installed."

    try:
        result = subprocess.run(
            [remote_path, "--torrent", str(torrent_id), "--stop"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return f"Torrent {torrent_id} paused."
        return f"Failed to pause torrent {torrent_id}: {result.stderr.strip() or 'Unknown error'}"
    except Exception as e:
        return f"Error: {e}"


@tool(
    name="torrent_resume",
    description="Resume a paused torrent in Transmission by its ID number.",
    params={
        "torrent_id": {
            "type": "integer",
            "description": "Torrent ID number (use torrent_status to find IDs)",
        },
    },
    required=["torrent_id"],
)
def torrent_resume(torrent_id: int) -> str:
    """Resume a paused torrent."""
    remote_path, _, _ = _locate_transmission()
    if remote_path is None:
        return "transmission-remote is not installed."

    try:
        result = subprocess.run(
            [remote_path, "--torrent", str(torrent_id), "--start"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return f"Torrent {torrent_id} resumed."
        return f"Failed to resume torrent {torrent_id}: {result.stderr.strip() or 'Unknown error'}"
    except Exception as e:
        return f"Error: {e}"
