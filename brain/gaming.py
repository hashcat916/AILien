"""Gaming engine — detects platforms, discovers games, manages configuration."""

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# Platform detection
# ──────────────────────────────────────────────────────────────────

def _which(name: str) -> str | None:
    """Check if a binary is on PATH and return its path."""
    path = shutil.which(name)
    return path


def _flatpak_is_installed(app_id: str) -> bool:
    """Check if a Flatpak app is installed."""
    try:
        r = subprocess.run(
            ["flatpak", "info", app_id],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def detect_gaming_setup() -> dict[str, Any]:
    """Scan the system for gaming tools and platforms.

    Returns a dict with boolean flags and paths for each component found.
    """
    result: dict[str, Any] = {
        "steam": False,
        "steam_path": None,
        "steamcmd": False,
        "lutris": False,
        "lutris_path": None,
        "heroic": False,
        "bottles": False,
        "gamemode": False,
        "gamemode_path": None,
        "mangohud": False,
        "mangohud_path": None,
        "gamescope": False,
        "gamescope_path": None,
        "protonup_qt": False,
        "legendary": False,
        "proton_versions": [],
        "wine_versions": [],
        "nvidia_gpu": False,
        "amd_gpu": False,
        "hybrid_graphics": False,
    }

    # ── Steam ──
    steam_bin = _which("steam")
    if steam_bin:
        result["steam"] = True
        result["steam_path"] = steam_bin
    # Also check Flatpak Steam
    if _flatpak_is_installed("com.valvesoftware.Steam"):
        result["steam"] = True
        result["steam_path"] = "flatpak run com.valvesoftware.Steam"

    # SteamCMD
    if _which("steamcmd") or _which("steamcmd.exe"):
        result["steamcmd"] = True

    # ── Lutris ──
    lutris_bin = _which("lutris")
    if lutris_bin:
        result["lutris"] = True
        result["lutris_path"] = lutris_bin
    if _flatpak_is_installed("net.lutris.Lutris"):
        result["lutris"] = True
        result["lutris_path"] = "flatpak run net.lutris.Lutris"

    # ── Heroic Games Launcher ──
    if _flatpak_is_installed("com.heroicgameslauncher.hgl"):
        result["heroic"] = True
    if _which("heroic"):
        result["heroic"] = True
    # Legendary (Heroic backend for Epic)
    if _which("legendary"):
        result["legendary"] = True

    # ── Bottles ──
    if _flatpak_is_installed("com.usebottles.bottles"):
        result["bottles"] = True
    if _which("bottles") or _which("bottles-cli"):
        result["bottles"] = True

    # ── GameMode ──
    gm_path = _which("gamemoderun")
    if gm_path:
        result["gamemode"] = True
        result["gamemode_path"] = gm_path
    # Check if libgamemode is installed (for auto-detection)
    if not gm_path and _which("gamemoded"):
        result["gamemode"] = True
        result["gamemode_path"] = "gamemoderun"

    # ── MangoHud ──
    mh_path = _which("mangohud")
    if mh_path:
        result["mangohud"] = True
        result["mangohud_path"] = mh_path

    # ── Gamescope ──
    gs_path = _which("gamescope")
    if gs_path:
        result["gamescope"] = True
        result["gamescope_path"] = gs_path

    # ── ProtonUp-Qt ──
    if _which("protonup-qt") or _which("protonup") or _flatpak_is_installed("net.davidotek.pupgui2"):
        result["protonup_qt"] = True

    # ── Proton versions (from Steam compatibility tools) ──
    compat_dir = Path.home() / ".steam/root/compatibilitytools.d"
    if compat_dir.exists():
        for p in compat_dir.iterdir():
            if p.is_dir() and (p / "proton").exists():
                result["proton_versions"].append(p.name)
    # Also check Steam's built-in Proton
    steam_path = _find_steam_path()
    if steam_path:
        built_in_proton = steam_path / "compatibilitytools.d"
        if built_in_proton.exists():
            for p in built_in_proton.iterdir():
                if p.is_dir() and (p / "proton").exists() and p.name not in result["proton_versions"]:
                    result["proton_versions"].append(p.name)
        # Steam's own proton (separate location)
        steam_proton = steam_path / "steamapps/common"
        for proton_dir in ["Proton - Experimental", "Proton 9.0", "Proton 8.0", "Proton 7.0", "Proton 5.0"]:
            if (steam_proton / proton_dir / "proton").exists():
                result["proton_versions"].append(proton_dir)

    # ── Wine versions ──
    if _which("wine"):
        try:
            r = subprocess.run(["wine", "--version"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                result["wine_versions"].append(r.stdout.strip())
        except Exception:
            pass
    # Check for Proton/wine inside Lutris
    lutris_runners = Path.home() / ".local/share/lutris/runners/wine"
    if lutris_runners.exists():
        for p in lutris_runners.iterdir():
            if p.is_dir():
                result["wine_versions"].append(f"Lutris: {p.name}")

    # ── GPU detection ──
    try:
        r = subprocess.run(
            ["lspci"],
            capture_output=True, text=True, timeout=10,
        )
        output = r.stdout.lower()
        if "nvidia" in output:
            result["nvidia_gpu"] = True
        if "amd" in output or "radeon" in output:
            result["amd_gpu"] = True
        # Hybrid graphics
        if _which("prime-select") or _which("optimus-manager"):
            result["hybrid_graphics"] = True
        if result.get("nvidia_gpu") and (result.get("amd_gpu") or "intel" in output):
            result["hybrid_graphics"] = True
    except Exception:
        pass

    return result


def _find_steam_path() -> Path | None:
    """Try to locate the Steam installation directory."""
    candidates = [
        Path.home() / ".steam/steam",
        Path.home() / ".local/share/Steam",
        Path.home() / "snap/steam/common/.local/share/Steam",
        Path("/usr/share/steam"),
        Path("/var/lib/flatpak/app/com.valvesoftware.Steam/current/active/files/share/Steam"),
    ]
    for p in candidates:
        if (p / "steamapps").exists():
            return p
    return None


# ──────────────────────────────────────────────────────────────────
# Game discovery
# ──────────────────────────────────────────────────────────────────

def _parse_acf(acf_path: Path) -> dict[str, Any] | None:
    """Parse a Steam .acf manifest file into a dict.

    .acf files use a simple key-value format with nested blocks.
    """
    try:
        text = acf_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    # Simple recursive parser for the Valve KeyValues format
    lines = text.splitlines()
    result: dict[str, Any] = {}
    stack: list[dict[str, Any]] = [result]
    current_key: str | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Skip comments
        if stripped.startswith("//") or stripped.startswith("#"):
            continue

        # Opening brace — new nested object
        if stripped == "{":
            if current_key:
                new_dict: dict[str, Any] = {}
                stack[-1][current_key] = new_dict
                stack.append(new_dict)
                current_key = None
            continue

        # Closing brace — pop back
        if stripped == "}":
            if len(stack) > 1:
                stack.pop()
            continue

        # Key-value or key with sub-block
        # Pattern: "key" "value" or "key" { ... }
        match = re.match(r'^"([^"]*)"\s*"([^"]*)"\s*$', stripped)
        if match:
            key, value = match.groups()
            stack[-1][key] = value
            current_key = None
            continue

        # Key (value follows on next line as block)
        match = re.match(r'^"([^"]+)"\s*$', stripped)
        if match:
            current_key = match.group(1)
            continue

    return result


def discover_steam_games() -> list[dict[str, Any]]:
    """Discover installed Steam games by parsing library folders.

    Checks the primary library and any additional libraryfolders.vdf entries.
    Returns a list of dicts with {app_id, name, install_dir, library_path}.
    """
    steam_path = _find_steam_path()
    if not steam_path:
        return []

    games: list[dict[str, Any]] = []
    seen_app_ids: set[str] = set()

    # Collect library paths (primary + secondary)
    library_paths: list[Path] = [steam_path]

    # Parse libraryfolders.vdf for additional libraries
    lf_vdf = steam_path / "steamapps/libraryfolders.vdf"
    if lf_vdf.exists():
        try:
            text = lf_vdf.read_text(encoding="utf-8", errors="replace")
            # Extract paths from lines like: "1" "/media/games/SteamLibrary"
            for match in re.finditer(r'"\d+"\s*"([^"]+)"', text):
                path_str = match.group(1)
                # Skip the "path" key inside content blocks
                if path_str and path_str.startswith("/"):
                    alt_lib = Path(path_str) / "steamapps"
                    if alt_lib.exists() and alt_lib not in library_paths:
                        library_paths.append(alt_lib.parent)
        except Exception as e:
            logger.debug("Failed to parse libraryfolders.vdf: %s", e)

    for lib_path in library_paths:
        apps_dir = lib_path / "steamapps"
        if not apps_dir.exists():
            continue

        for acf_file in sorted(apps_dir.glob("*.acf")):
            try:
                data = _parse_acf(acf_file)
                if data is None:
                    continue

                app_id = data.get("appid", "")
                if app_id in seen_app_ids:
                    continue
                seen_app_ids.add(app_id)

                name = data.get("name", "Unknown")
                install_dir_str = data.get("installdir", "")

                games.append({
                    "app_id": app_id,
                    "name": name,
                    "install_dir": install_dir_str,
                    "library_path": str(lib_path),
                    "platform": "steam",
                })
            except Exception as e:
                logger.debug("Failed to parse %s: %s", acf_file, e)
                continue

    # Sort by name
    games.sort(key=lambda g: g["name"].lower())
    return games


def discover_lutris_games() -> list[dict[str, Any]]:
    """Discover games from Lutris by reading its SQLite database or YAML config."""
    games: list[dict[str, Any]] = []

    # Lutris stores game info in ~/.config/lutris/games/ as YAML files
    lutris_games_dir = Path.home() / ".config/lutris/games"
    if not lutris_games_dir.exists():
        # Also check XDG config
        xdg = os.getenv("XDG_CONFIG_HOME")
        if xdg:
            lutris_games_dir = Path(xdg) / "lutris/games"

    if not lutris_games_dir.exists():
        # Try the SQLite database
        lutris_db = Path.home() / ".local/share/lutris/pga.db"
        if lutris_db.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(str(lutris_db))
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, slug, runner FROM games")
                for row in cursor.fetchall():
                    if row[1]:  # name
                        games.append({
                            "id": str(row[0]),
                            "name": row[1],
                            "slug": row[2] or "",
                            "runner": row[3] or "linux",
                            "platform": "lutris",
                        })
                conn.close()
                return games
            except Exception as e:
                logger.debug("Failed to read Lutris SQLite DB: %s", e)
        return games

    # Parse YAML files (each game)
    for yaml_file in lutris_games_dir.glob("*.yml"):
        try:
            import yaml
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if data and isinstance(data, dict):
                name = data.get("name", data.get("game", {}).get("slug", yaml_file.stem))
                if name:
                    games.append({
                        "id": yaml_file.stem,
                        "name": name,
                        "slug": data.get("game", {}).get("slug", yaml_file.stem),
                        "runner": data.get("runner", "linux"),
                        "platform": "lutris",
                        "yaml_path": str(yaml_file),
                    })
        except Exception as e:
            logger.debug("Failed to parse Lutris YAML %s: %s", yaml_file, e)
            continue

    games.sort(key=lambda g: g["name"].lower())
    return games


def discover_heroic_games() -> list[dict[str, Any]]:
    """Discover games from Heroic Games Launcher (Epic/GOG via config files)."""
    games: list[dict[str, Any]] = []

    # Heroic stores config in ~/.config/heroic/
    heroic_config = Path.home() / ".config/heroic"
    if not heroic_config.exists():
        return games

    # Legendary (Epic) installed games
    legendary_installed = Path.home() / ".config/legendary/installed.json"
    if legendary_installed.exists():
        try:
            data = json.loads(legendary_installed.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for app_name, info in data.items():
                    title = info.get("title", app_name)
                    games.append({
                        "app_name": app_name,
                        "name": title,
                        "platform": "heroic_epic",
                        "install_path": info.get("install_path", ""),
                        "version": info.get("version", ""),
                    })
        except Exception as e:
            logger.debug("Failed to parse Legendary installed.json: %s", e)

    # GOG games from Heroic
    heroic_gog = heroic_config / "gog_store/installed.json"
    if heroic_gog.exists():
        try:
            data = json.loads(heroic_gog.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for game in data:
                    if isinstance(game, dict) and game.get("title"):
                        games.append({
                            "app_name": game.get("app_name", ""),
                            "name": game["title"],
                            "platform": "heroic_gog",
                            "install_path": game.get("install_path", ""),
                            "version": game.get("version", ""),
                        })
        except Exception as e:
            logger.debug("Failed to parse Heroic GOG installed.json: %s", e)

    games.sort(key=lambda g: g["name"].lower())
    return games


def discover_all_games() -> list[dict[str, Any]]:
    """Discover installed games from all supported platforms.

    Returns a combined, deduplicated list of all games.
    """
    all_games: list[dict[str, Any]] = []

    try:
        all_games.extend(discover_steam_games())
    except Exception as e:
        logger.debug("Steam game discovery failed: %s", e)

    try:
        all_games.extend(discover_lutris_games())
    except Exception as e:
        logger.debug("Lutris game discovery failed: %s", e)

    try:
        all_games.extend(discover_heroic_games())
    except Exception as e:
        logger.debug("Heroic game discovery failed: %s", e)

    all_games.sort(key=lambda g: g["name"].lower())
    return all_games


def find_game(query: str) -> dict[str, Any] | None:
    """Find a game by name (partial, case-insensitive match).

    Returns the first match or None.
    """
    query_lower = query.lower().strip()
    games = discover_all_games()

    # Try exact match first
    for g in games:
        if g["name"].lower() == query_lower:
            return g

    # Try partial match
    for g in games:
        if query_lower in g["name"].lower():
            return g

    # Try word-by-word matching
    query_words = query_lower.split()
    best_match = None
    best_score = 0
    for g in games:
        name_lower = g["name"].lower()
        score = sum(1 for w in query_words if w in name_lower)
        if score > best_score:
            best_score = score
            best_match = g

    if best_score > 0:
        return best_match

    return None


# ──────────────────────────────────────────────────────────────────
# Game launching
# ──────────────────────────────────────────────────────────────────

def _build_prefix(use_gamemode: bool, use_mangohud: bool, use_gamescope: bool,
                    resolution: str, fps_limit: int, gpu: str) -> tuple[list[str], dict[str, str]]:
    """Build a command prefix and env vars for performance optimizations.

    Returns (prefix_cmd_parts, env_vars).
    """
    prefix_parts: list[str] = []
    env: dict[str, str] = {}
    setup = detect_gaming_setup()

    # ── GPU offloading for hybrid graphics ──
    if gpu:
        gpu_lower = gpu.lower()
        if gpu_lower in ("nvidia", "dedicated", "dgpu") and _which("prime-run"):
            prefix_parts.append("prime-run")
        elif gpu_lower in ("nvidia", "dedicated", "dgpu"):
            env["__NV_PRIME_RENDER_OFFLOAD"] = "1"
            env["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
        elif gpu_lower in ("amd", "intel"):
            env["DRI_PRIME"] = "1"

    # ── Gamescope (must come first as it starts its own compositor) ──
    if use_gamescope and setup.get("gamescope"):
        gs_opts = ["gamescope"]
        if resolution:
            parts = resolution.lower().split("x")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                gs_opts.extend(["-w", parts[0], "-h", parts[1]])
        if fps_limit > 0:
            gs_opts.extend(["-r", str(fps_limit)])
        gs_opts.append("--")
        prefix_parts = gs_opts + prefix_parts

    # ── GameMode ──
    if use_gamemode and setup.get("gamemode"):
        prefix_parts.append("gamemoderun")

    # ── MangoHud ──
    if use_mangohud and setup.get("mangohud"):
        prefix_parts.append("mangohud")

    return prefix_parts, env


def launch_steam_game(app_id: str, use_gamemode: bool = True, use_gamescope: bool = False,
                      resolution: str = "", fps_limit: int = 0, gpu: str = "") -> str:
    """Launch a Steam game by app ID.

    Steam games: uses steam://run/ URL to launch via the Steam client.
    Performance tools (GameMode, MangoHud, Gamescope) should be configured
    in Steam's per-game launch options for best results — this function
    launches cleanly through Steam stdandard mechanism.
    GPU env vars (DRI_PRIME, __NV_PRIME_RENDER_OFFLOAD) are applied since
    they are inherited by Steam child processes.
    """
    setup = detect_gaming_setup()

    if setup.get("steam_path") and "flatpak" in setup["steam_path"]:
        cmd_parts = ["flatpak", "run", "com.valvesoftware.Steam"]
    else:
        cmd_parts = ["steam"]

    cmd_parts.append(f"steam://run/{app_id}")

    # Apply GPU offloading env vars (inherited by Steam child processes)
    env = os.environ.copy()
    if gpu:
        gpu_lower = gpu.lower()
        if gpu_lower in ("nvidia", "dedicated", "dgpu"):
            env["__NV_PRIME_RENDER_OFFLOAD"] = "1"
            env["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
        elif gpu_lower in ("amd", "intel"):
            env["DRI_PRIME"] = "1"

    try:
        subprocess.Popen(
            cmd_parts,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        gpu_hint = f" on {gpu.upper()} GPU" if gpu else ""
        return (f"Launching Steam game (app ID: {app_id}){gpu_hint}. "
                "For GameMode/MangoHud/Gamescope optimizations, configure them "
                "in Steam's per-game launch options.")
    except Exception as e:
        return f"Failed to launch Steam game: {e}"


def launch_game_by_name(name: str, use_gamemode: bool = True,
                         use_gamescope: bool = False, resolution: str = "",
                         fps_limit: int = 0, use_mangohud: bool = True,
                         gpu: str = "") -> str:
    """Launch a game by name, auto-detecting the platform."""
    game = find_game(name)
    if not game:
        return f"Could not find a game matching '{name}'. Use 'list_games' to see installed games."

    platform = game.get("platform", "")

    if platform == "steam":
        return launch_steam_game(
            game["app_id"],
            use_gamemode=use_gamemode,
            use_gamescope=use_gamescope,
            resolution=resolution,
            fps_limit=fps_limit,
        )

    elif platform == "lutris":
        setup = detect_gaming_setup()
        lutris_path = setup.get("lutris_path", "lutris")
        game_id = game.get("id") or game.get("slug", "")

        prefix_parts, env = _build_prefix(
            use_gamemode=use_gamemode,
            use_mangohud=use_mangohud,
            use_gamescope=use_gamescope,
            resolution=resolution,
            fps_limit=fps_limit,
            gpu=gpu,
        )

        cmd_parts = prefix_parts + [lutris_path, f"lutris:rungame/{game_id}"]
        subprocess.Popen(
            cmd_parts if cmd_parts else [lutris_path, f"lutris:rungame/{game_id}"],
            env={**os.environ, **env} if env else None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"Launching '{game['name']}' via Lutris with performance optimizations."

    elif platform.startswith("heroic"):
        app_name = game.get("app_name", "")
        if not app_name:
            return f"Game '{game['name']}' has no app name for launching."

        setup = detect_gaming_setup()

        if not setup.get("legendary"):
            return (f"Game '{game['name']}' is a Heroic/Epic game, but the Legendary CLI is not on PATH. "
                    "You can launch this game from the Heroic Games Launcher GUI, or install legendary-gl "
                    "with: sudo pip install legendary-gl")

        prefix_parts, env = _build_prefix(
            use_gamemode=use_gamemode,
            use_mangohud=use_mangohud,
            use_gamescope=use_gamescope,
            resolution=resolution,
            fps_limit=fps_limit,
            gpu=gpu,
        )

        cmd_parts = prefix_parts + ["legendary", "launch", app_name]
        subprocess.Popen(
            cmd_parts if cmd_parts else ["legendary", "launch", app_name],
            env={**os.environ, **env} if env else None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"Launching '{game['name']}' via Legendary (Heroic/Epic) with performance optimizations."

    return f"Unknown platform '{platform}' for game '{game['name']}'."


# ──────────────────────────────────────────────────────────────────
# Gaming configuration
# ──────────────────────────────────────────────────────────────────

def configure_gamemode(enabled: bool = True) -> str:
    """Enable or disable GameMode daemon."""
    if not _which("gamemoded"):
        return "GameMode is not installed. Install it with: sudo apt install gamemode (Ubuntu) or sudo pacman -S gamemode (Arch)"

    try:
        if enabled:
            # Ensure the service is running
            subprocess.run(["systemctl", "--user", "start", "gamemoded"], capture_output=True, timeout=5)
            return "GameMode enabled — system will now optimize for gaming automatically."
        else:
            subprocess.run(["systemctl", "--user", "stop", "gamemoded"], capture_output=True, timeout=5)
            return "GameMode disabled."
    except Exception as e:
        return f"Failed to configure GameMode: {e}"


def configure_gpu_power(mode: str = "auto") -> str:
    """Set GPU power profile.

    Args:
        mode: 'auto', 'high', 'low' for AMD; or check nvidia-settings for NVIDIA.
    """
    setup = detect_gaming_setup()
    if setup.get("nvidia_gpu"):
        try:
            if mode == "high":
                subprocess.run(
                    ["nvidia-settings", "-a", "[gpu:0]/GpuPowerMizerMode=1"],
                    capture_output=True, timeout=10,
                )
                return "NVIDIA GPU set to maximum performance mode."
            elif mode == "low":
                subprocess.run(
                    ["nvidia-settings", "-a", "[gpu:0]/GpuPowerMizerMode=0"],
                    capture_output=True, timeout=10,
                )
                return "NVIDIA GPU set to power-saving mode."
            else:
                return "NVIDIA GPU left in auto mode."
        except Exception as e:
            return f"Failed to set NVIDIA power mode: {e}"

    if setup.get("amd_gpu"):
        try:
            # AMD GPU power profile via sysfs
            gpu_path = "/sys/class/drm/card0/device/power_dpm_force_performance_level"
            if os.path.exists(gpu_path):
                mapping = {"high": "high", "low": "low", "auto": "auto"}
                level = mapping.get(mode, "auto")
                Path(gpu_path).write_text(level)
                return f"AMD GPU power profile set to '{level}'."
            else:
                return "AMD GPU power control not available on this system."
        except Exception as e:
            return f"Failed to set AMD power profile: {e}"

    return "No compatible GPU detected for power configuration."


def configure_hybrid_graphics(mode: str = "on-demand") -> str:
    """Configure NVIDIA Optimus / hybrid graphics mode.

    Args:
        mode: 'nvidia', 'intel', 'on-demand', or 'auto'
    """
    if _which("prime-select"):
        try:
            subprocess.run(
                ["sudo", "prime-select", mode],
                capture_output=True, text=True, timeout=15,
            )
            return f"Graphics mode set to '{mode}'. Log out and back in for changes to take effect."
        except Exception as e:
            return f"Failed to set graphics mode: {e}"

    if _which("optimus-manager"):
        try:
            subprocess.run(
                ["optimus-manager", "--switch", mode],
                capture_output=True, text=True, timeout=15,
            )
            return f"Graphics mode switched to '{mode}'."
        except Exception as e:
            return f"Failed to switch graphics mode: {e}"

    return "No hybrid graphics manager found. Install prime-select or optimus-manager."


# ──────────────────────────────────────────────────────────────────
# Bottles management
# ──────────────────────────────────────────────────────────────────

def bottles_list_bottles() -> list[dict[str, str]]:
    """List available Bottles."""
    bottles: list[dict[str, str]] = []

    # Try bottles-cli first
    bottles_cli = _which("bottles-cli")
    if bottles_cli:
        try:
            r = subprocess.run(
                [bottles_cli, "list", "bottles"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                # Parse output — bottles-cli returns JSON or text
                for line in r.stdout.strip().splitlines():
                    if line.strip() and ":" in line:
                        name = line.split(":")[0].strip()
                        bottles.append({"name": name, "platform": "bottles"})
        except Exception as e:
            logger.debug("bottles-cli failed: %s", e)

    # Fallback: read Bottles config files
    bottles_dir = Path.home() / ".var/app/com.usebottles.bottles/data/bottles/bottles"
    if not bottles_dir.exists():
        bottles_dir = Path.home() / ".local/share/bottles/bottles"

    if bottles_dir.exists():
        for bottle_dir in bottles_dir.iterdir():
            if bottle_dir.is_dir() and not bottle_dir.name.startswith("."):
                config_file = bottle_dir / "bottle.yml"
                if config_file.exists():
                    bottles.append({"name": bottle_dir.name, "platform": "bottles", "path": str(bottle_dir)})

    return bottles


def bottles_list_programs(bottle_name: str) -> list[dict[str, str]]:
    """List programs installed in a specific Bottle."""
    programs: list[dict[str, str]] = []

    bottles_cli = _which("bottles-cli")
    if bottles_cli:
        try:
            r = subprocess.run(
                [bottles_cli, "programs", "-b", bottle_name],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                for line in r.stdout.strip().splitlines():
                    if line.strip():
                        programs.append({"name": line.strip(), "bottle": bottle_name, "platform": "bottles"})
        except Exception as e:
            logger.debug("bottles-cli programs failed: %s", e)

    return programs


# ──────────────────────────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────────────────────────

def check_gaming_health() -> dict[str, Any]:
    """Run a comprehensive gaming health check.

    Checks:
      - Which platforms are installed
      - Are gaming performance tools installed (GameMode, MangoHud, Gamescope)
      - GPU driver status
      - Number of games per platform
      - Kernel and distro info
      - Any missing recommended packages
    """
    setup = detect_gaming_setup()
    health: dict[str, Any] = {
        "status": "ok",
        "issues": [],
        "recommendations": [],
        "platforms": {},
        "performance_tools": {},
        "gpu": {},
        "game_counts": {},
        "kernel_version": "",
        "distro": "",
    }

    # ── Platforms ──
    health["platforms"] = {
        "steam": setup["steam"],
        "lutris": setup["lutris"],
        "heroic": setup["heroic"],
        "bottles": setup["bottles"],
        "legendary_cli": setup["legendary"],
    }

    # ── Performance tools ──
    health["performance_tools"] = {
        "gamemode": setup["gamemode"],
        "mangohud": setup["mangohud"],
        "gamescope": setup["gamescope"],
        "protonup_qt": setup["protonup_qt"],
    }

    # ── GPU ──
    health["gpu"] = {
        "nvidia": setup["nvidia_gpu"],
        "amd": setup["amd_gpu"],
        "hybrid_graphics": setup["hybrid_graphics"],
    }

    # ── Game counts ──
    try:
        steam_games = discover_steam_games()
        health["game_counts"]["steam"] = len(steam_games)
    except Exception:
        health["game_counts"]["steam"] = 0

    try:
        lutris_games = discover_lutris_games()
        health["game_counts"]["lutris"] = len(lutris_games)
    except Exception:
        health["game_counts"]["lutris"] = 0

    try:
        heroic_games = discover_heroic_games()
        health["game_counts"]["heroic"] = len(heroic_games)
    except Exception:
        health["game_counts"]["heroic"] = 0

    total_games = sum(health["game_counts"].values())
    health["total_games"] = total_games

    # ── Kernel / distro ──
    try:
        r = subprocess.run(["uname", "-r"], capture_output=True, text=True, timeout=5)
        health["kernel_version"] = r.stdout.strip()
    except Exception:
        pass

    try:
        # Check various distro files
        for distro_file in ["/etc/os-release", "/etc/lsb-release"]:
            if os.path.exists(distro_file):
                text = Path(distro_file).read_text()
                for line in text.splitlines():
                    if line.startswith("PRETTY_NAME="):
                        health["distro"] = line.split("=", 1)[1].strip('"')
                        break
                if health["distro"]:
                    break
    except Exception:
        pass

    # ── Issues and recommendations ──
    if not setup["gamemode"]:
        health["issues"].append("GameMode not installed — reduces stutter and improves frame rates.")
        health["recommendations"].append("Install GameMode: sudo apt install gamemode (Ubuntu/Debian) or sudo pacman -S gamemode (Arch)")

    if not setup["mangohud"]:
        health["recommendations"].append("Install MangoHud for in-game performance overlay: sudo apt install mangohud (Ubuntu) or sudo pacman -S mangohud (Arch)")

    if not setup["gamescope"]:
        health["recommendations"].append("Install Gamescope for FSR upscaling and game-specific resolutions: sudo apt install gamescope (Ubuntu) or sudo pacman -S gamescope (Arch)")

    if not setup["protonup_qt"]:
        health["recommendations"].append("Install ProtonUp-Qt to easily manage Proton/Wine versions for better game compatibility")

    if health["game_counts"].get("steam", 0) == 0:
        health["recommendations"].append("No Steam games found — install Steam and download some games first")

    if total_games == 0:
        health["status"] = "no_games"
        health["issues"].append("No games found on any platform.")
    elif len(health["issues"]) > 0:
        health["status"] = "partial"
    else:
        health["status"] = "ready"

    return health
