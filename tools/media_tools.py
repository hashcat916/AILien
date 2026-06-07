"""Local media playback tools — find and play movies/music from the PC."""

import shutil
import subprocess
import time
from pathlib import Path

from tools import tool

# Common media directories to search
MEDIA_DIRS = [
    Path.home() / "Music",
    Path.home() / "Videos",
    Path.home() / "Movies",
    Path.home() / "Downloads",
]

# Common media file extensions
MEDIA_EXTENSIONS = {
    ".mp3", ".flac", ".wav", ".aac", ".ogg", ".wma", ".m4a", ".opus",      # audio
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",       # video
    ".mpeg", ".mpg", ".3gp", ".ts", ".mts", ".m2ts",
}

# Preferred players in order
PLAYERS = ["celluloid", "vlc", "mpv", "ffplay", "xdg-open"]


def _find_player() -> str | None:
    """Find an available media player."""
    import shutil
    for player in PLAYERS:
        path = shutil.which(player)
        if path:
            return path
    return None


def _search_media(query: str, max_results: int = 20) -> list[Path]:
    """Search for media files matching *query* under *MEDIA_DIRS*."""
    query_lower = query.lower()
    matches: list[Path] = []

    for media_dir in MEDIA_DIRS:
        if not media_dir.is_dir():
            continue
        try:
            for f in media_dir.rglob("*"):
                if len(matches) >= max_results:
                    break
                if not f.is_file():
                    continue
                if f.suffix.lower() not in MEDIA_EXTENSIONS:
                    continue
                # Match against the filename (without extension)
                if query_lower in f.stem.lower():
                    matches.append(f)
        except PermissionError:
            continue

    return matches


@tool(
    name="play_media",
    description="Search for and play a local movie, music file, or video by name.",
    params={
        "query": {
            "type": "string",
            "description": "Name or partial name of the media file to search for (e.g. 'feel good', 'avatar', 'song title')",
        },
        "player": {
            "type": "string",
            "description": "Player to use: 'default' (auto-select), 'celluloid', 'vlc', 'mpv', or 'ffplay'",
            "default": "default",
        },
    },
    required=["query"],
)
def play_media(query: str, player: str = "default") -> str:
    """Search for media files matching *query* and play the best match."""
    if not query.strip():
        return "Please provide a search term."

    matches = _search_media(query)

    if not matches:
        # Try a broader search if nothing found
        for media_dir in MEDIA_DIRS:
            if not media_dir.is_dir():
                continue
            try:
                entries = list(media_dir.iterdir())
                if entries:
                    return (
                        f"No media found matching '{query}'. "
                        f"Files in {media_dir.name}: "
                        + ", ".join(
                            e.stem for e in entries[:20]
                            if e.is_file() and e.suffix.lower() in MEDIA_EXTENSIONS
                        )
                    )
            except PermissionError:
                continue
        return (
            f"No media found matching '{query}'. "
            f"Checked directories: {', '.join(str(d) for d in MEDIA_DIRS if d.is_dir())}."
        )

    # Pick the best match
    target = matches[0]
    if len(matches) > 1:
        # Prefer exact stem match over partial
        exact = [m for m in matches if m.stem.lower() == query.lower()]
        if exact:
            target = exact[0]

    # Determine the player binary
    player_bin: str | None = _find_player()
    if player.lower() != "default":
        import shutil
        player_bin = shutil.which(player)

    if player_bin is None:
        return "No media player found. Install celluloid, vlc, or mpv."

    try:
        if "celluloid" in player_bin:
            # Celluloid opens in GUI mode by default
            subprocess.Popen(
                [player_bin, str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif "ffplay" in player_bin:
            # ffplay is terminal-based — detach with nohup
            subprocess.Popen(
                ["nohup", player_bin, "-nodisp", "-autoexit", str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif "xdg-open" in player_bin:
            subprocess.Popen(
                [player_bin, str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [player_bin, str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        time.sleep(0.5)
        player_name = Path(player_bin).name
        fsize = target.stat().st_size / (1024**2)
        return (
            f"Now playing '{target.stem}' ({fsize:.0f} MB) with {player_name}.\n"
            f"Path: {target}"
        )
    except Exception as e:
        return f"Failed to play media: {e}"


@tool(
    name="list_media",
    description="List available media files in your Music, Videos, Movies, and Downloads folders.",
    params={
        "directory": {
            "type": "string",
            "description": "Directory name to browse: 'music', 'videos', 'downloads', or 'all'",
            "default": "all",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum files to show (default 30)",
            "default": 30,
        },
    },
    required=[],
)
def list_media(directory: str = "all", max_results: int = 30) -> str:
    """List available media files in the user's media directories."""
    dirs_to_check: list[Path] = []

    if directory.lower() in ("music", "audio", "songs"):
        dirs_to_check = [Path.home() / "Music"]
    elif directory.lower() in ("videos", "video", "movies", "movie"):
        dirs_to_check = [Path.home() / "Videos", Path.home() / "Movies"]
    elif directory.lower() in ("downloads", "dl"):
        dirs_to_check = [Path.home() / "Downloads"]
    else:
        dirs_to_check = MEDIA_DIRS

    results: list[str] = []
    for d in dirs_to_check:
        if not d.is_dir():
            continue
        try:
            for f in sorted(d.iterdir()):
                if len(results) >= max_results:
                    break
                if not f.is_file():
                    continue
                if f.suffix.lower() not in MEDIA_EXTENSIONS:
                    continue
                size = f.stat().st_size / (1024**2)
                kind = "🎵" if f.suffix.lower() in {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".opus"} else "🎬"
                results.append(f"{kind}  {f.stem:40s}  {size:6.0f} MB  ({d.name})")
        except PermissionError:
            continue

    header = f"{'Type':4}  {'Name':40s}  {'Size':>6}  {'Location'}\n{'─'*70}"
    if not results:
        return f"No media files found in {', '.join(str(d) for d in dirs_to_check if d.is_dir())}."

    return header + "\n" + "\n".join(results)
