#!/bin/bash
# One-command install for voice-input on a new Apple Silicon Mac.
# Usage: ./setup.sh
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
step() { echo -e "\n${BOLD}── $1${NC}"; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       Voice Input — Installer        ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

# ── 0. Apple Silicon check ────────────────────────────────────────────────────
step "System check"
ARCH=$(uname -m)
if [ "$ARCH" != "arm64" ]; then
    fail "Apple Silicon (arm64) required — mlx-whisper does not run on Intel."
    exit 1
fi
ok "Apple Silicon detected"
SW_VERS=$(sw_vers -productVersion)
ok "macOS $SW_VERS"

# ── 1. Homebrew ───────────────────────────────────────────────────────────────
step "Homebrew"
if ! command -v brew &>/dev/null; then
    echo "  Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    [[ -f /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
fi
ok "Homebrew $(brew --version | head -1 | awk '{print $2}')"

# ── 2. Python 3.11+ ───────────────────────────────────────────────────────────
step "Python"
PY_OK=false
for py in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$py" &>/dev/null; then
        VER=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
            PYTHON="$py"
            PY_OK=true
            break
        fi
    fi
done

if ! $PY_OK; then
    echo "  Python 3.11+ not found — installing via Homebrew..."
    brew install python@3.12
    hash -r
    PYTHON=python3.12
fi
ok "Python $($PYTHON --version | awk '{print $2}')"

# ── 4. Python venv + packages ─────────────────────────────────────────────────
step "Python packages"
if [ -d .venv ]; then
    # Recreate venv if Python executable is gone (e.g. venv from old path)
    VENV_PY=".venv/bin/python"
    if ! "$VENV_PY" -c "import sys" &>/dev/null 2>&1; then
        echo "  Stale venv detected — recreating..."
        rm -rf .venv
    fi
fi

if [ ! -d .venv ]; then
    "$PYTHON" -m venv .venv
fi

.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
ok "All packages installed"

# ── 5. Pre-download Whisper model ─────────────────────────────────────────────
step "Whisper model (large-v3, Apple Silicon)"
MODEL_REPO="mlx-community/whisper-large-v3-mlx"
CACHE_DIR="$HOME/.cache/huggingface/hub"
MODEL_CACHED=false
if ls "$CACHE_DIR" 2>/dev/null | grep -q "whisper-large-v3-mlx"; then
    MODEL_CACHED=true
fi

if $MODEL_CACHED; then
    ok "Model already cached"
else
    echo "  Downloading (~1.5 GB) — this takes a few minutes..."
    .venv/bin/python - <<'PYEOF'
import mlx_whisper, numpy as np, sys
print("  Downloading model...", flush=True)
mlx_whisper.transcribe(
    np.zeros(16000, dtype="float32"),
    path_or_hf_repo="mlx-community/whisper-large-v3-mlx",
    language="ru", verbose=False,
)
print("  Model ready.", flush=True)
PYEOF
    ok "Model downloaded and warmed up"
fi

# ── 6. launchd auto-start ─────────────────────────────────────────────────────
step "Auto-start (launchd)"
./install_launchd.sh install
ok "Voice input service started"
ok "Menu bar app started"

# ── 7. macOS permissions ──────────────────────────────────────────────────────
step "macOS Permissions"
echo ""
echo "  Voice Input needs 3 permissions to work fully."
echo "  Each step opens System Settings — grant the permission, then return here."
echo "  You can skip any step and grant permissions later via the menu bar icon."
echo ""
echo "  In each panel, look for 'python3' under ~/voice-input/.venv/bin/"
echo "  and enable the toggle next to it."
echo ""

# 7a. Microphone
echo -e "  ${BOLD}1/3  Microphone${NC} — allows the app to record audio"
read -r -p "      Press Enter to open System Settings…"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"
echo ""
read -r -p "      Done? Press Enter to continue…"
echo ""

# 7b. Input Monitoring
echo -e "  ${BOLD}2/3  Input Monitoring${NC} — allows the app to detect the Right Cmd hotkey"
read -r -p "      Press Enter to open System Settings…"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
echo ""
read -r -p "      Done? Press Enter to continue…"
echo ""

# 7c. Accessibility
echo -e "  ${BOLD}3/3  Accessibility${NC} — allows the app to paste text at the cursor"
read -r -p "      Press Enter to open System Settings…"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
echo ""
read -r -p "      Done? Press Enter to continue…"
echo ""

# ── 8. Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Done ──────────────────────────────────────────────────────────────${NC}"
echo ""
ok "Whisper large-v3 (Apple Silicon)"
ok "launchd auto-start (voice input + menu bar)"
echo ""
echo "  Look for the microphone icon in the top-right menu bar."
echo "  Click it to switch language, select microphone, check permissions, or update."
echo ""
echo "  Hotkey:"
echo "    Right Cmd  (hold → release)  record speech → paste transcribed text"
echo ""
echo "  To stop:    ./install_launchd.sh stop"
echo "  To remove:  ./install_launchd.sh uninstall"
echo ""
