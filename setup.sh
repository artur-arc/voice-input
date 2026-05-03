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

# ── 6. macOS permissions ──────────────────────────────────────────────────────
step "macOS permissions"
echo ""
echo "  Three permissions are required."
echo "  A System Settings pane will open for each."
echo "  Find 'python' or 'Terminal' in the list and enable the toggle."
echo ""
read -r -p "  Press Enter to start…"

# Helper: open privacy pane and wait for user confirmation
request_perm() {
    local name="$1"
    local url="$2"
    local check_cmd="$3"
    local index="$4"

    echo ""
    echo -e "  ${BOLD}→ $index  $name${NC}"

    if eval "$check_cmd" &>/dev/null 2>&1; then
        ok "$name already granted"
        return 0
    fi

    open "$url"
    echo "    Enable the toggle for Python/Terminal, then press Enter…"
    read -r -p "    "

    if eval "$check_cmd" &>/dev/null 2>&1; then
        ok "$name granted"
    else
        warn "$name not detected — you can grant it later and rerun setup."
    fi
}

# 6a. Microphone
MIC_CHECK='.venv/bin/python -c "
import sounddevice as sd, numpy as np
sd.rec(100, samplerate=16000, channels=1, dtype=\"float32\", blocking=True)
"'
request_perm \
    "Microphone (recording your voice)" \
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone" \
    "$MIC_CHECK" \
    "1/3"

# 6b. Input Monitoring
IM_CHECK='.venv/bin/python -c "
from pynput import keyboard
import threading, time
done = threading.Event()
def stop(k): done.set(); return False
l = keyboard.Listener(on_press=stop)
l.start()
done.wait(timeout=0.3)
l.stop()
if not done.is_set(): raise RuntimeError(\"no events\")
"'
request_perm \
    "Input Monitoring (detecting hotkey)" \
    "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent" \
    "$IM_CHECK" \
    "2/3"

# 6c. Accessibility
AX_CHECK='.venv/bin/python -c "
import sys; sys.path.insert(0,\"src\")
from paste_util import has_accessibility
import sys; sys.exit(0 if has_accessibility() else 1)
"'
# Trigger the system prompt dialog automatically
.venv/bin/python - <<'PYEOF' 2>/dev/null || true
import sys; sys.path.insert(0, "src")
from ApplicationServices import AXIsProcessTrustedWithOptions
AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
PYEOF
request_perm \
    "Accessibility (pasting text at cursor)" \
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" \
    "$AX_CHECK" \
    "3/3"

# ── 7. launchd auto-start ─────────────────────────────────────────────────────
step "Auto-start (launchd)"
./install_launchd.sh install
ok "Runs at login, starts now in background"

# ── 8. Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Done ──────────────────────────────────────────────────────────────${NC}"
echo ""

# Verify final state
AX_OK=$(.venv/bin/python -c "import sys; sys.path.insert(0,'src'); from paste_util import has_accessibility; print(has_accessibility())" 2>/dev/null)
MIC_OK=$(.venv/bin/python -c "import sounddevice as sd, numpy as np; sd.rec(100,samplerate=16000,channels=1,dtype='float32',blocking=True); print('ok')" 2>/dev/null | grep -c ok || echo 0)

echo "  Status:"
[ "$AX_OK" = "True" ] && ok "Accessibility (auto-paste)" || warn "Accessibility not granted — paste disabled"
[ "$MIC_OK" -gt 0   ] && ok "Microphone" || warn "Microphone not granted — recording disabled"
ok "Whisper large-v3 (Apple Silicon)"
ok "launchd auto-start"
echo ""
echo "  Hotkeys:"
echo "    Right Cmd  (hold → release)  record & paste"
echo "    Right Option (tap)           cycle mode: ru→en / ru→ru / en→en"
echo ""
echo "  Config: $(pwd)/voice-input-config.json"
echo "  Logs:   tail -f $(pwd)/voice_input.log"
echo ""
echo "  To stop:    ./install_launchd.sh stop"
echo "  To remove:  ./install_launchd.sh uninstall"
echo ""
