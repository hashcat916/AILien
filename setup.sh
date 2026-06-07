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
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
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
# Create skills and conversations directories
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

# Generate icons for desktop shortcuts
icons = {
    '$SCRIPT_DIR/icons/ailien_icon.png': None,
    '$SCRIPT_DIR/icons/ailien_icon_128.png': None,
}

for path, color in icons.items():
    size = 128 if '128' in path else 64
    icon = generate_alien_icon(256)
    final = icon.resize((size, size), __import__('PIL').Image.LANCZOS)
    final.save(path)
    print(f'  Generated {path.split("/")[-1]}')
"
ok "Icons generated."

# ------------------------------------------------------------------
# Desktop shortcuts
# ------------------------------------------------------------------
DESKTOP_DIR="$HOME/Desktop"
if [ -d "$DESKTOP_DIR" ]; then
    info "Creating desktop shortcuts..."

    create_shortcut() {
        local name="$1"
        local comment="$2"
        local exec_cmd="$3"
        local icon="$4"
        local file="$DESKTOP_DIR/$name.desktop"

        cat > "$file" << EOF
[Desktop Entry]
Name=$name
Comment=$comment
Exec=bash -c "cd $SCRIPT_DIR && ./ailien $exec_cmd"
Type=Application
Terminal=true
Icon=$SCRIPT_DIR/$icon
Categories=Utility;System;
StartupNotify=true
EOF
        chmod +x "$file"
        ok "Created shortcut: $file"
    }

    create_shortcut "AILIEN" "AI computer control assistant — wake word mode" "--daemon" "icons/ailien_icon_128.png"
    create_shortcut "AILIEN-Text" "AILIEN — terminal text chat mode" "--text" "icons/ailien_icon.png"
    create_shortcut "AILIEN-Voice" "AILIEN — voice interactive mode" "--voice" "icons/ailien_icon.png"
    create_shortcut "AILIEN-Server" "AILIEN — HTTP API server for Open WebUI" "--serve" "icons/ailien_icon.png"
else
    warn "Desktop directory not found at $DESKTOP_DIR. Skipping shortcuts."
fi

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
echo "    source .venv/bin/activate"
echo "    export GROQ_API_KEY=\"gsk_...\""
echo "    python main.py"
echo ""
echo "  Or use desktop shortcuts:"
echo "    AILIEN         → Wake word mode (default)"
echo "    AILIEN-Text    → Chat via text"
echo "    AILIEN-Voice   → Push-to-talk voice"
echo "    AILIEN-Server  → HTTP API for Open WebUI"
echo ""
echo "  New features:"
echo "    python main.py --conversation conv.json   → Load a conversation"
echo "    python main.py --list-conversations        → List saved chats"
echo "    python main.py -c \"open firefox\" --save-conversation result.json"
echo ""
echo "  Skills: Add .py files to skills/ to extend AILIEN!"
echo "  See skills/example_skill.py for a template."
echo ""
