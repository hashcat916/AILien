#!/usr/bin/env bash
# ===========================================================================
# AILIEN — One-command setup script
# ===========================================================================
# This script sets up everything you need to run AILIEN:
#   1. Creates a Python virtual environment
#   2. Installs Python dependencies
#   3. Installs system dependencies (Linux)
#   4. Generates application icons
#   5. Creates desktop shortcuts
#   6. Installs optional torrent support (transmission-cli)
#
# Usage:
#   chmod +x setup.sh && ./setup.sh
#
# Or for a quiet install (non-interactive):
#   ./setup.sh --quiet
# ===========================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUIET="${1:-}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

cd "$SCRIPT_DIR"

# ------------------------------------------------------------------
# Check Python
# ------------------------------------------------------------------
info "Checking Python 3.10+..."
PYTHON=""
for cmd in python3 python3.12 python3.11 python3.10; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    error "Python 3.10+ is required but not found."
    error "Install it with: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi
ok "Using $PYTHON ($($PYTHON --version))"

# ------------------------------------------------------------------
# System dependencies (Linux)
# ------------------------------------------------------------------
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    info "Checking system dependencies..."
    DEPS=(
        python3-pip python3-venv python3-tk
        portaudio19-dev ffmpeg
        libx11-dev libxtst-dev libxinerama-dev
        xdotool
    )
    MISSING=()
    for dep in "${DEPS[@]}"; do
        if ! dpkg -l "$dep" &>/dev/null 2>&1; then
            MISSING+=("$dep")
        fi
    done
    if [ ${#MISSING[@]} -gt 0 ]; then
        info "Installing missing system packages: ${MISSING[*]}"
        if [[ $EUID -eq 0 ]]; then
            apt-get update -qq && apt-get install -y -qq "${MISSING[@]}"
        else
            sudo apt-get update -qq && sudo apt-get install -y -qq "${MISSING[@]}"
        fi
        ok "System packages installed."
    else
        ok "All system packages present."
    fi

    # Optional: install transmission-cli for torrent tools
    if command -v transmission-remote &>/dev/null; then
        ok "transmission-cli already installed."
    else
        info "Installing transmission-cli for torrent support..."
        if [[ $EUID -eq 0 ]]; then
            apt-get install -y -qq transmission-cli transmission-daemon 2>/dev/null
        else
            sudo apt-get install -y -qq transmission-cli transmission-daemon 2>/dev/null
        fi
        if command -v transmission-remote &>/dev/null; then
            ok "transmission-cli installed."
        else
            warn "transmission-cli not installed (apt may have been locked)."
            warn "Run: sudo apt-get install transmission-cli transmission-daemon"
        fi
    fi
fi

# ------------------------------------------------------------------
# Python virtual environment
# ------------------------------------------------------------------
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment..."
    $PYTHON -m venv "$VENV_DIR"
    ok "Virtual environment created at $VENV_DIR"
else
    ok "Virtual environment exists at $VENV_DIR"
fi

# Activate
source "$VENV_DIR/bin/activate"

# Upgrade pip
info "Upgrading pip..."
pip install --quiet --upgrade pip setuptools wheel
ok "Pip upgraded."

# Install requirements
info "Installing Python dependencies..."
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
    ok "Python dependencies installed."
else
    warn "No requirements.txt found."
fi

# ------------------------------------------------------------------
# Create essential directories
# ------------------------------------------------------------------
mkdir -p "$SCRIPT_DIR/skills" "$SCRIPT_DIR/conversations"
ok "Skills and conversations directories ready."

# ------------------------------------------------------------------
# Generate icons
# ------------------------------------------------------------------
info "Generating application icons..."
$PYTHON -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from generate_icon import generate_alien_icon

for name, size in [('ailien_icon.png', 64), ('ailien_icon_128.png', 128)]:
    icon = generate_alien_icon(256)
    final = icon.resize((size, size), __import__('PIL').Image.LANCZOS)
    final.save(f'icons/{name}')
    print(f'  Generated {name}')
" 2>/dev/null || info "Icon generation skipped (will use fallback)"
ok "Icons generated."

# ------------------------------------------------------------------
# Desktop shortcuts + application menu entries
# ------------------------------------------------------------------
create_shortcut() {
    local name="$1"
    local comment="$2"
    local exec_cmd="$3"
    local icon="$4"
    local terminal="${5:-true}"

    # Install to Desktop (if directory exists)
    if [ -d "$DESKTOP_DIR" ]; then
        file="$DESKTOP_DIR/$name.desktop"
        _write_desktop_entry "$file" "$name" "$comment" "$exec_cmd" "$icon" "$terminal"
        chmod +x "$file"
        if command -v gio &>/dev/null; then
            gio set "$file" "metadata::trusted" true 2>/dev/null || true
        fi
        ok "Desktop shortcut: $file"
    fi

    # Install to application menu (whisker menu)
    file="$APPS_DIR/$name.desktop"
    _write_desktop_entry "$file" "$name" "$comment" "$exec_cmd" "$icon" "$terminal"
    chmod +x "$file"
    ok "App menu entry: $file"
}

_write_desktop_entry() {
    local file="$1" name="$2" comment="$3" exec_cmd="$4" icon="$5" terminal="$6"
    cat > "$file" << EOF
[Desktop Entry]
Version=1.0
Name=$name
Comment=$comment
Exec=$SCRIPT_DIR/ailien $exec_cmd
Icon=$SCRIPT_DIR/$icon
Type=Application
Terminal=$terminal
Categories=Utility;System;
StartupNotify=true
EOF
}

DESKTOP_DIR="$HOME/Desktop"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"

create_shortcut "AILIEN" "AI computer control assistant — background daemon with tray icon" "--daemon" "icons/ailien_icon_128.png" "false"
create_shortcut "AILIEN-Text" "AILIEN — terminal text chat mode" "--text" "icons/ailien_icon.png"
create_shortcut "AILIEN-Voice" "AILIEN — voice interactive mode" "--voice" "icons/ailien_icon.png"
create_shortcut "AILIEN-Server" "AILIEN — HTTP API server for Open WebUI" "--serve" "icons/ailien_icon.png"

# ------------------------------------------------------------------
# Done
# ------------------------------------------------------------------
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           AILIEN setup complete! 👽              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Quick start:"
echo "    cd $SCRIPT_DIR"
echo "    ./ailien --text"
echo ""
echo "  First, set your API key in a .env file:"
echo "    echo \"XAI_API_KEY=xai-...\" > .env"
echo "    # or: export XAI_API_KEY=\"xai-...\""
echo ""
echo "  Or use desktop shortcuts:"
echo "    AILIEN           → Background daemon (tray icon)"
echo "    AILIEN-Text      → Text chat"
echo "    AILIEN-Voice     → Push-to-talk voice"
echo "    AILIEN-Server    → HTTP API for Open WebUI"
echo ""
echo "  Try these commands:"
echo "    ./ailien -c \"what's my system status?\""
echo "    ./ailien -c \"open firefox and go to youtube.com\""
echo "    ./ailien -c \"set a timer for 30 seconds\""
echo "    ./ailien -c \"remind me in 5 minutes to check email\""
echo "    ./ailien -c \"what's the weather?\""
echo ""
echo "  87 tools available. Type anything — AILIEN figures out the right tool."
echo ""
