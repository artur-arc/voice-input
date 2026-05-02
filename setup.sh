#!/bin/bash
# One-command setup for voice-input on a new Mac.
# Usage: ./setup.sh
set -e
cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════╗"
echo "║      Voice Input — Setup         ║"
echo "╚══════════════════════════════════╝"
echo ""

# ── 1. Python ────────────────────────────────────────────────────────────────
ensure_python() {
    # Returns true if python3 >= 3.9 is available
    command -v python3 &>/dev/null && \
        python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null
}

install_homebrew() {
    echo "  Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for the rest of this script (Apple Silicon path)
    [[ -f /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
    [[ -f /usr/local/bin/brew   ]] && eval "$(/usr/local/bin/brew shellenv)"
}

if ! ensure_python; then
    PY_DESC=$(python3 --version 2>/dev/null || echo "not found")
    echo "  Python 3.9+ required (found: $PY_DESC) — installing via Homebrew..."

    if ! command -v brew &>/dev/null; then
        install_homebrew
    fi

    brew install python
    hash -r  # refresh PATH cache
fi

if ! ensure_python; then
    echo "✗ Python 3.9+ still not found after install. Fix manually and re-run."
    exit 1
fi

PY=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python $PY"

# ── 2. Virtualenv + dependencies ─────────────────────────────────────────────
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
echo "✓ Dependencies installed"

# ── 3. launchd auto-start ────────────────────────────────────────────────────
./install_launchd.sh install
echo "✓ Auto-start configured (starts at login, runs in background)"

# ── 4. macOS permissions ─────────────────────────────────────────────────────
echo ""
echo "── macOS Permissions ──────────────────────────────────────────────────"
echo ""
echo "  3 permissions are required. System Settings will open for each."
echo "  In each pane: find 'Python' or 'python3' → enable the toggle."
echo ""
read -r -p "  Press Enter to open System Settings…"
echo ""

echo "  → 1/3  Microphone (for recording your voice)"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"
sleep 1

echo "  → 2/3  Input Monitoring (to detect hotkey press)"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
sleep 1

echo "  → 3/3  Accessibility (to paste text into other apps)"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"

# ── 5. Done ──────────────────────────────────────────────────────────────────
echo ""
echo "── Done ────────────────────────────────────────────────────────────────"
echo ""
echo "  After granting all 3 permissions, voice-input is running in the"
echo "  background and will start automatically at every login."
echo ""
echo "  Hotkeys:"
echo "    Right Cmd (hold)   → record, release → transcribe & paste"
echo "    Right Option (tap) → cycle mode: ru→en / ru→ru / en→en"
echo ""
echo "  ⚠  First run downloads the Whisper 'medium' model (~1.5 GB)."
echo "     Watch: tail -f $(pwd)/voice_input.log"
echo ""
echo "  To stop:      ./install_launchd.sh stop"
echo "  To remove:    ./install_launchd.sh uninstall"
echo ""
