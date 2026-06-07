"""Gaming tools — detect platforms, launch games, configure performance."""

from typing import Any

from brain.gaming import (
    check_gaming_health,
    configure_gamemode,
    configure_gpu_power,
    configure_hybrid_graphics,
    detect_gaming_setup,
    discover_all_games,
    find_game,
    launch_game_by_name,
    launch_steam_game,
)
from tools import tool


@tool(
    name="detect_gaming_setup",
    description="Scan the system for installed gaming platforms and performance tools. Detects Steam, Lutris, Heroic Games Launcher, Bottles, GameMode, MangoHud, Gamescope, GPU type, and Proton versions.",
    params={},
    required=[],
)
def detect_gaming_setup_tool() -> str:
    """Scan the system for gaming tools and platforms."""
    result = detect_gaming_setup()
    lines = ["🎮 Gaming Setup Detection", "────────────────────────"]

    # Platforms
    platforms = []
    if result["steam"]:
        platforms.append("✓ Steam")
    if result["lutris"]:
        platforms.append("✓ Lutris")
    if result["heroic"]:
        platforms.append("✓ Heroic Games Launcher")
    if result["bottles"]:
        platforms.append("✓ Bottles")
    if not platforms:
        platforms.append("— No gaming platforms detected")

    lines.append(f"Platforms: {' | '.join(platforms)}")

    # Performance tools
    perf_tools = []
    if result["gamemode"]:
        perf_tools.append("✓ GameMode")
    if result["mangohud"]:
        perf_tools.append("✓ MangoHud")
    if result["gamescope"]:
        perf_tools.append("✓ Gamescope")
    if result["protonup_qt"]:
        perf_tools.append("✓ ProtonUp-Qt")

    lines.append(f"Performance: {' | '.join(perf_tools) if perf_tools else '— None detected'}")

    # GPU
    gpu_info = []
    if result["nvidia_gpu"]:
        gpu_info.append("NVIDIA")
    if result["amd_gpu"]:
        gpu_info.append("AMD")
    if result["hybrid_graphics"]:
        gpu_info.append("(Hybrid/Optimus)")

    lines.append(f"GPU: {' + '.join(gpu_info) if gpu_info else 'Not detected'}")
    lines.append(f"Proton versions: {', '.join(result['proton_versions']) if result['proton_versions'] else 'None'}")
    lines.append(f"Wine versions: {', '.join(result['wine_versions'][:5]) if result['wine_versions'] else 'None'}")

    return "\n".join(lines)


@tool(
    name="list_games",
    description="List all installed games discovered from Steam, Lutris, and Heroic Games Launcher. Optionally filter by platform or search by name.",
    params={
        "platform": {"type": "string", "description": "Filter by platform: 'steam', 'lutris', 'heroic', or empty for all", "default": ""},
        "search": {"type": "string", "description": "Search query to filter games by name", "default": ""},
    },
    required=[],
)
def list_games(platform: str = "", search: str = "") -> str:
    """List all installed games, optionally filtered by platform."""
    games = discover_all_games()
    if not games:
        return "No games found. Install Steam, Lutris, or Heroic Games Launcher and download some games first."

    # Filter by platform
    if platform:
        platform_lower = platform.lower().strip()
        if platform_lower == "steam":
            games = [g for g in games if g["platform"] == "steam"]
        elif platform_lower in ("lutris",):
            games = [g for g in games if g["platform"] == "lutris"]
        elif platform_lower in ("heroic", "epic", "gog"):
            games = [g for g in games if g["platform"].startswith("heroic")]
        else:
            return f"Unknown platform '{platform}'. Supported: steam, lutris, heroic"

    # Filter by search
    if search:
        query = search.lower()
        games = [g for g in games if query in g["name"].lower()]

    if not games:
        msg = "No games found"
        if platform:
            msg += f" on {platform}"
        if search:
            msg += f" matching '{search}'"
        return msg + "."

    # Format output by platform
    from collections import defaultdict
    by_platform: dict[str, list[str]] = defaultdict(list)
    platform_labels = {
        "steam": "🎮 Steam",
        "lutris": "🐧 Lutris",
        "heroic_epic": "🟣 Heroic (Epic)",
        "heroic_gog": "🟡 Heroic (GOG)",
    }

    for g in games:
        label = platform_labels.get(g.get("platform", ""), g.get("platform", "Unknown"))
        by_platform[label].append(g["name"])

    lines = [f"📋 Games Found: {len(games)}"]
    lines.append("─" * 40)

    for plat in sorted(by_platform.keys()):
        game_list = by_platform[plat]
        lines.append(f"\n{plat} ({len(game_list)}):")
        for name in game_list:
            lines.append(f"  • {name}")

    return "\n".join(lines)


@tool(
    name="launch_game",
    description="Launch a game by name. Auto-detects the platform (Steam, Lutris, Heroic/Epic) and optionally applies performance optimizations like GameMode, Gamescope, resolution scaling, FPS limits, or GPU offloading for hybrid graphics.",
    params={
        "name": {"type": "string", "description": "Game name to launch (partial match works)"},
        "gamemode": {"type": "boolean", "description": "Use GameMode for performance optimization (default true for Lutris/Heroic, has no effect on Steam games — configure in Steam's per-game launch options)", "default": True},
        "gamescope": {"type": "boolean", "description": "Use Gamescope compositor for resolution/FSR control (default false)", "default": False},
        "resolution": {"type": "string", "description": "Resolution for Gamescope, e.g. '1920x1080' (requires gamescope=true)", "default": ""},
        "fps_limit": {"type": "integer", "description": "FPS limit (requires gamescope=true)", "default": 0},
        "mangohud": {"type": "boolean", "description": "Show MangoHud performance overlay (default true for non-Steam games)", "default": True},
        "gpu": {"type": "string", "description": "GPU to use on hybrid laptops: 'nvidia', 'amd', 'intel', 'dedicated', or empty for default", "default": ""},
    },
    required=["name"],
)
def launch_game_tool(name: str, gamemode: bool = True, gamescope: bool = False,
                     resolution: str = "", fps_limit: int = 0,
                     mangohud: bool = True, gpu: str = "") -> str:
    """Launch a game by name with optional optimizations."""
    return launch_game_by_name(
        name,
        use_gamemode=gamemode,
        use_gamescope=gamescope,
        resolution=resolution,
        fps_limit=fps_limit,
        use_mangohud=mangohud,
        gpu=gpu,
    )


@tool(
    name="configure_gaming",
    description="Configure gaming performance settings: GameMode on/off, GPU power profile (high/auto/low), or hybrid graphics mode (nvidia/intel/on-demand).",
    params={
        "gamemode": {"type": "boolean", "description": "Enable or disable GameMode daemon (leave empty to skip)"},
        "gpu_power": {"type": "string", "description": "GPU power profile: 'high', 'auto', or 'low' (leave empty to skip)"},
        "hybrid_graphics": {"type": "string", "description": "Hybrid graphics mode: 'nvidia', 'intel', 'on-demand', or 'auto' (leave empty to skip)"},
    },
    required=[],
)
def configure_gaming(gamemode: bool | None = None, gpu_power: str = "",
                     hybrid_graphics: str = "") -> str:
    """Configure gaming performance settings."""
    results: list[str] = []

    if gamemode is not None:
        results.append(configure_gamemode(enabled=gamemode))

    if gpu_power and gpu_power.strip():
        if gpu_power.lower() in ("high", "auto", "low"):
            results.append(configure_gpu_power(mode=gpu_power.lower()))
        else:
            results.append(f"Invalid GPU power mode '{gpu_power}'. Use: high, auto, low")

    if hybrid_graphics and hybrid_graphics.strip():
        valid_modes = ("nvidia", "intel", "on-demand", "auto")
        if hybrid_graphics.lower() in valid_modes:
            results.append(configure_hybrid_graphics(mode=hybrid_graphics.lower()))
        else:
            results.append(f"Invalid hybrid mode '{hybrid_graphics}'. Use: nvidia, intel, on-demand, auto")

    if not results:
        return ("No settings provided. Options:\n"
                "  • gamemode=true/false — enable/disable GameMode\n"
                "  • gpu_power=high/auto/low — GPU power profile\n"
                "  • hybrid_graphics=nvidia/intel/on-demand — GPU switching")

    return "\n".join(results)


@tool(
    name="check_gaming_setup",
    description="Run a comprehensive gaming health check. Detects installed platforms, performance tools, GPU drivers, and provides recommendations for missing components.",
    params={},
    required=[],
)
def check_gaming_setup_tool() -> str:
    """Run a comprehensive gaming health check."""
    health = check_gaming_health()

    status_emoji = {"ready": "✅", "partial": "⚠️", "no_games": "📦", "ok": "✅"}
    emoji = status_emoji.get(health.get("status", "ok"), "❓")

    lines = [f"{emoji} Gaming Health Check", "─" * 40]

    # Status
    lines.append(f"\nStatus: {health.get('status', 'unknown').upper()}")

    # Platforms
    platforms = health.get("platforms", {})
    plat_status = []
    for name, installed in platforms.items():
        icon = "✓" if installed else "✗"
        plat_status.append(f"{icon} {name.capitalize()}")
    lines.append(f"Platforms: {' | '.join(plat_status)}")

    # Performance tools
    perf = health.get("performance_tools", {})
    perf_status = []
    for name, installed in perf.items():
        icon = "✓" if installed else "✗"
        perf_status.append(f"{icon} {name}")
    lines.append(f"Tools: {' | '.join(perf_status)}")

    # GPU
    gpu = health.get("gpu", {})
    gpu_parts = []
    if gpu.get("nvidia"):
        gpu_parts.append("NVIDIA")
    if gpu.get("amd"):
        gpu_parts.append("AMD")
    if gpu.get("hybrid_graphics"):
        gpu_parts.append("(Hybrid)")
    lines.append(f"GPU: {' + '.join(gpu_parts) if gpu_parts else 'Not detected'}")

    # Kernel / Distro
    distro = health.get("distro", "Unknown")
    kernel = health.get("kernel_version", "")
    lines.append(f"OS: {distro} | Kernel: {kernel}")

    # Game counts
    counts = health.get("game_counts", {})
    total = health.get("total_games", 0)
    count_str = " | ".join(f"{k}: {v}" for k, v in counts.items() if v > 0)
    lines.append(f"Games installed: {total} ({count_str})")

    # Issues
    issues = health.get("issues", [])
    if issues:
        lines.append(f"\n❌ Issues ({len(issues)}):")
        for issue in issues:
            lines.append(f"  • {issue}")

    # Recommendations
    recs = health.get("recommendations", [])
    if recs:
        lines.append(f"\n💡 Recommendations:")
        for rec in recs:
            lines.append(f"  • {rec}")

    return "\n".join(lines)


@tool(
    name="install_gaming_tool",
    description="Get installation instructions for a gaming-related tool. Supports: gamemode, mangohud, gamescope, protonup-qt, lutris, heroic-games-launcher, bottles, steam.",
    params={
        "tool_name": {"type": "string", "description": "Name of the tool to install: gamemode, mangohud, gamescope, protonup-qt, lutris, heroic-games-launcher, bottles, steam"},
    },
    required=["tool_name"],
)
def install_gaming_tool(tool_name: str) -> str:
    """Provide installation instructions for a gaming tool."""
    instructions = {
        "gamemode": (
            "GameMode — automatic system optimization while gaming\n"
            "  Ubuntu/Debian: sudo apt install gamemode\n"
            "  Fedora: sudo dnf install gamemode\n"
            "  Arch: sudo pacman -S gamemode\n"
            "  Use: add 'gamemoderun %command%' to Steam launch options"
        ),
        "mangohud": (
            "MangoHud — in-game performance overlay (FPS, temps, GPU/CPU usage)\n"
            "  Ubuntu/Debian: sudo apt install mangohud\n"
            "  Fedora: sudo dnf install mangohud\n"
            "  Arch: sudo pacman -S mangohud\n"
            "  Flatpak: flatpak install flathub org.freedesktop.Platform.VulkanLayer.MangoHud\n"
            "  Use: add 'mangohud %command%' to Steam launch options"
        ),
        "gamescope": (
            "Gamescope — gaming micro-compositor (FSR upscaling, custom resolutions)\n"
            "  Ubuntu/Debian: sudo apt install gamescope\n"
            "  Fedora: sudo dnf install gamescope\n"
            "  Arch: sudo pacman -S gamescope\n"
            "  Use: add 'gamescope -w 1920 -h 1080 -- %command%' to Steam launch options"
        ),
        "protonup-qt": (
            "ProtonUp-Qt — manage Proton/Wine versions for better compatibility\n"
            "  Flatpak (recommended): flatpak install flathub net.davidotek.pupgui2\n"
            "  Arch: sudo pacman -S protonup-qt\n"
            "  Use: launch the app to install custom Proton versions (GE-Proton, etc.)"
        ),
        "lutris": (
            "Lutris — game manager for native, Wine/Proton, and emulated games\n"
            "  Ubuntu/Debian: sudo add-apt-repository ppa:lutris-team/lutris && sudo apt update && sudo apt install lutris\n"
            "  Fedora: sudo dnf install lutris\n"
            "  Arch: sudo pacman -S lutris\n"
            "  Flatpak: flatpak install flathub net.lutris.Lutris"
        ),
        "heroic-games-launcher": (
            "Heroic Games Launcher — Epic Games and GOG client for Linux\n"
            "  Flatpak (recommended): flatpak install flathub com.heroicgameslauncher.hgl\n"
            "  Arch: yay -S heroic-games-launcher-bin\n"
            "  Also installs Legendary CLI for Epic games: sudo pip install legendary-gl"
        ),
        "bottles": (
            "Bottles — Wine prefix manager for running Windows apps/games\n"
            "  Flatpak (recommended): flatpak install flathub com.usebottles.bottles\n"
            "  Arch: sudo pacman -S bottles\n"
            "  Use: bottles-cli run -b <bottle> -p <program>"
        ),
        "steam": (
            "Steam — the largest PC gaming platform\n"
            "  Ubuntu/Debian: sudo apt install steam\n"
            "  Fedora: sudo dnf install steam\n"
            "  Arch: sudo pacman -S steam\n"
            "  Flatpak: flatpak install flathub com.valvesoftware.Steam"
        ),
    }

    key = tool_name.lower().strip()
    if key in instructions:
        return instructions[key]
    else:
        supported = ", ".join(sorted(instructions.keys()))
        return f"Unknown tool '{tool_name}'. Supported tools: {supported}"
