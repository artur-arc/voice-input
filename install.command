#!/bin/bash
# Universal installer — macOS (double-click in Finder) or Windows (run via Git Bash).
# Handles Homebrew and Python installation (bash-only tasks), then delegates to setup.py.
set -e

REPO="https://github.com/artur-arc/voice-input.git"

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }

clear
echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       Voice Input — Installer        ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""
echo "  This will take a few minutes. Do not close this window."
echo ""

# ── Platform detection ────────────────────────────────────────────────────────
_OS="$(uname -s)"
case "$_OS" in
  Darwin)
    PLATFORM="mac"
    INSTALL_DIR="$HOME/voice-input"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    PLATFORM="windows"
    INSTALL_DIR="$HOME/voice-input"   # Git Bash maps $HOME to %USERPROFILE%
    ;;
  *)
    fail "Unsupported platform: $_OS. Supported: macOS and Windows (via Git Bash)."
    ;;
esac
ok "Platform: $PLATFORM"

# ── macOS: Apple Silicon + Homebrew + Python ──────────────────────────────────
if [ "$PLATFORM" = "mac" ]; then
    [ "$(uname -m)" != "arm64" ] && fail "Apple Silicon (M1/M2/M3/M4) required."

    echo -e "${BOLD}── Homebrew${NC}"
    if ! command -v brew &>/dev/null; then
        echo "  Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        [[ -f /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    ok "Homebrew ready"

    echo -e "${BOLD}── Python${NC}"
    PYTHON=""
    for py in python3.14 python3.13 python3.12 python3.11 python3; do
        if command -v "$py" &>/dev/null; then
            MINOR=$("$py" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
            [ "${MINOR:-0}" -ge 11 ] && PYTHON="$py" && break
        fi
    done
    if [ -z "$PYTHON" ]; then
        echo "  Python 3.11+ not found — installing via Homebrew..."
        brew install python@3.12
        hash -r
        PYTHON=python3.12
    fi
    ok "Python $("$PYTHON" --version | awk '{print $2}')"
fi

# ── Windows: Python check ─────────────────────────────────────────────────────
if [ "$PLATFORM" = "windows" ]; then
    echo -e "${BOLD}── Python${NC}"
    PYTHON=""
    for candidate in python3 python; do
        if command -v "$candidate" &>/dev/null; then
            MINOR=$("$candidate" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
            [ "${MINOR:-0}" -ge 11 ] && PYTHON="$candidate" && break
        fi
    done
    [ -z "$PYTHON" ] && fail "Python 3.11+ not found. Install from https://www.python.org/downloads/ (check 'Add Python to PATH')"
    ok "Python $("$PYTHON" --version | awk '{print $2}')"
fi

# ── Git ───────────────────────────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
    [ "$PLATFORM" = "mac" ] && brew install git || fail "Git not found. Install from https://git-scm.com/download/win"
fi

# ── Clone or update ───────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Downloading Voice Input${NC}"
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  Updating to latest version..."
    git -C "$INSTALL_DIR" pull --ff-only
    ok "Updated"
else
    [ -d "$INSTALL_DIR" ] && { warn "Removing existing directory..."; rm -rf "$INSTALL_DIR"; }
    echo "  Cloning..."
    git clone "$REPO" "$INSTALL_DIR"
    ok "Downloaded to $INSTALL_DIR"
fi

# ── Run setup ─────────────────────────────────────────────────────────────────
cd "$INSTALL_DIR"
"$PYTHON" setup.py
