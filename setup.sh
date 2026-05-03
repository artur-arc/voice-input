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
echo "  macOS will ask for 3 permissions. Click 'Allow' in each dialog."
echo ""

# Waits in a loop until check_cmd exits 0, printing a dot every second.
wait_for_perm() {
    local check_cmd="$1"
    local max=60
    local i=0
    while ! eval "$check_cmd" &>/dev/null 2>&1; do
        sleep 1
        i=$((i+1))
        printf "."
        if [ "$i" -ge "$max" ]; then
            echo ""
            warn "Timed out. Re-run ./setup.sh after granting the permission."
            return 1
        fi
    done
    echo ""
    return 0
}

# 6a. Microphone — macOS shows native dialog automatically on first access
echo -e "  ${BOLD}1/3  Microphone${NC}"
.venv/bin/python - <<'PYEOF' 2>/dev/null || true
import sounddevice as sd, numpy as np
try:
    sd.rec(100, samplerate=16000, channels=1, dtype="float32", blocking=True)
except Exception:
    pass
PYEOF
MIC_CHECK='.venv/bin/python -c "
import sounddevice as sd, numpy as np
sd.rec(100, samplerate=16000, channels=1, dtype=\"float32\", blocking=True)
"'
if eval "$MIC_CHECK" &>/dev/null 2>&1; then
    ok "Microphone — granted"
else
    echo "    Click 'Allow' in the macOS dialog..."
    wait_for_perm "$MIC_CHECK" && ok "Microphone — granted" || true
fi

# 6b. Input Monitoring — pynput triggers native dialog on first listener start
echo ""
echo -e "  ${BOLD}2/3  Input Monitoring${NC} (hotkey detection)"
.venv/bin/python - <<'PYEOF' 2>/dev/null || true
from pynput import keyboard as kb
import threading
done = threading.Event()
listener = kb.Listener(on_press=lambda k: done.set())
listener.start()
done.wait(timeout=0.5)
listener.stop()
PYEOF
IM_CHECK='.venv/bin/python -c "
from pynput import keyboard as kb
import threading
done = threading.Event()
l = kb.Listener(on_press=lambda k: done.set())
l.start(); done.wait(timeout=0.3); l.stop()
if not done.is_set(): raise RuntimeError()
"'
if eval "$IM_CHECK" &>/dev/null 2>&1; then
    ok "Input Monitoring — granted"
else
    echo "    Click 'Allow' in the dialog, then press any key..."
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
    wait_for_perm "$IM_CHECK" && ok "Input Monitoring — granted" || true
fi

# 6c. Accessibility — trigger the system prompt dialog
echo ""
echo -e "  ${BOLD}3/3  Accessibility${NC} (paste text at cursor)"
.venv/bin/python - <<'PYEOF' 2>/dev/null || true
from ApplicationServices import AXIsProcessTrustedWithOptions
AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
PYEOF
AX_CHECK='.venv/bin/python -c "
import sys; sys.path.insert(0,\"src\")
from paste_util import has_accessibility
sys.exit(0 if has_accessibility() else 1)
"'
if eval "$AX_CHECK" &>/dev/null 2>&1; then
    ok "Accessibility — granted"
else
    echo "    System Settings opened → find 'Terminal' or 'python' → enable the toggle."
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
    echo "    Press Enter when done..."
    read -r -p "    "
    eval "$AX_CHECK" &>/dev/null 2>&1 && ok "Accessibility — granted" \
        || warn "Accessibility not granted — text will be copied to clipboard only."
fi

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
