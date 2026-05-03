#!/bin/bash
# Double-click this file to install Voice Input.
# macOS opens it in Terminal automatically.
set -e

REPO="https://github.com/artur-arc/voice-input.git"
INSTALL_DIR="$HOME/voice-input"

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

# ── Apple Silicon check ───────────────────────────────────────────────────────
if [ "$(uname -m)" != "arm64" ]; then
    fail "Apple Silicon (M1/M2/M3/M4) required. For Windows, use install.bat instead."
fi

# ── Homebrew ──────────────────────────────────────────────────────────────────
echo -e "${BOLD}── Homebrew${NC}"
if ! command -v brew &>/dev/null; then
    echo "  Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    [[ -f /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
fi
ok "Homebrew ready"

# ── Git ───────────────────────────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
    echo "  Installing git..."
    brew install git
fi

# ── Download project ──────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Downloading Voice Input${NC}"
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  Updating to latest version..."
    git -C "$INSTALL_DIR" pull --ff-only
    ok "Updated"
else
    if [ -d "$INSTALL_DIR" ]; then
        warn "$INSTALL_DIR exists but is not a git repo — removing..."
        rm -rf "$INSTALL_DIR"
    fi
    echo "  Cloning..."
    git clone "$REPO" "$INSTALL_DIR"
    ok "Downloaded to $INSTALL_DIR"
fi

# ── Run main installer ────────────────────────────────────────────────────────
cd "$INSTALL_DIR"
bash setup.sh
