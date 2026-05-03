#!/usr/bin/env python3
"""Cross-platform setup for voice-input — macOS and Windows from one script.

Called by install.command (macOS / Windows Git Bash) after Python is confirmed available.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent
IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

# Platform-specific venv paths
if IS_WINDOWS:
    VENV_PY   = REPO_DIR / ".venv" / "Scripts" / "python.exe"
    VENV_PYW  = REPO_DIR / ".venv" / "Scripts" / "pythonw.exe"
    VENV_PIP  = REPO_DIR / ".venv" / "Scripts" / "pip.exe"
    REQUIREMENTS = REPO_DIR / "requirements-windows.txt"
else:
    VENV_PY   = REPO_DIR / ".venv" / "bin" / "python3"
    VENV_PYW  = VENV_PY  # no separate pythonw on macOS
    VENV_PIP  = REPO_DIR / ".venv" / "bin" / "pip"
    REQUIREMENTS = REPO_DIR / "requirements.txt"

_MAC_MODEL  = "mlx-community/whisper-large-v3-mlx"
_WIN_MODEL  = "large-v3"

GREEN = "\033[0;32m"
BOLD  = "\033[1m"
NC    = "\033[0m"


def ok(msg: str)   -> None: print(f"  {GREEN}✓{NC} {msg}")
def step(msg: str) -> None: print(f"\n{BOLD}── {msg}{NC}")


# ── Steps ─────────────────────────────────────────────────────────────────────

def create_venv() -> None:
    venv_path = REPO_DIR / ".venv"
    if venv_path.exists():
        try:
            subprocess.run(
                [str(VENV_PY), "-c", "import sys"],
                check=True, capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("  Stale venv detected — recreating...")
            shutil.rmtree(venv_path)
    if not venv_path.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    ok("Virtual environment ready")


def install_packages() -> None:
    key_pkg = "faster-whisper" if IS_WINDOWS else "mlx-whisper"
    r = subprocess.run(
        [str(VENV_PY), "-m", "pip", "show", key_pkg],
        capture_output=True,
    )
    if r.returncode == 0:
        ok("Packages already installed")
        return
    subprocess.run(
        [str(VENV_PY), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
        check=True,
    )
    label = "ctranslate2 is ~150 MB" if IS_WINDOWS else "mlx-whisper is ~300 MB"
    print(f"  Installing packages ({label} — please wait)...")
    subprocess.run(
        [str(VENV_PY), "-m", "pip", "install", "--progress-bar", "on", "-r", str(REQUIREMENTS)],
        check=True,
    )
    ok("All packages installed")


def download_model() -> None:
    env = os.environ.copy()
    env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    env["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    if IS_MAC:
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        if cache_dir.exists() and any(cache_dir.glob("*whisper-large-v3-mlx*")):
            ok("Model already cached")
            return
        print("  Downloading (~1.5 GB) — this takes a few minutes...")
        script = (
            "import mlx_whisper, numpy as np; "
            f"mlx_whisper.transcribe(np.zeros(16000, dtype='float32'), "
            f"path_or_hf_repo='{_MAC_MODEL}', language='ru', verbose=False); "
            "print('  Model ready.')"
        )
        subprocess.run([str(VENV_PY), "-c", script], check=True, env=env)
    else:
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        if cache_dir.exists() and any(cache_dir.glob("*faster-whisper-large-v3*")):
            ok("Model already cached")
            return
        print("  Downloading faster-whisper large-v3 (~1.5 GB) — this takes a few minutes...")
        # Write a script file: tqdm must be patched before faster_whisper is imported
        # so that huggingface_hub picks up our subclass (which forces disable=False).
        dl = REPO_DIR / "_dl.py"
        dl.write_text(
            "import sys, tqdm\n"
            "try:\n"
            "    import tqdm.auto as _ta\n"
            "except ImportError:\n"
            "    _ta = None\n"
            "\n"
            "class _P(tqdm.tqdm):\n"
            "    def __init__(self, *a, **k):\n"
            "        k['disable'] = False\n"
            "        super().__init__(*a, **k)\n"
            "\n"
            "tqdm.tqdm = _P\n"
            "if _ta:\n"
            "    _ta.tqdm = _P\n"
            "try:\n"
            "    import huggingface_hub.utils._tqdm as _h\n"
            "    _h.tqdm = _P\n"
            "except Exception:\n"
            "    pass\n"
            "\n"
            "from faster_whisper import WhisperModel\n"
            f"WhisperModel('{_WIN_MODEL}', device='cpu', compute_type='int8')\n"
            "print('  Model ready.', flush=True)\n",
            encoding="utf-8",
        )
        try:
            subprocess.run([str(VENV_PY), str(dl)], check=True, env=env)
        finally:
            dl.unlink(missing_ok=True)

    ok("Model downloaded and warmed up")


def setup_autostart() -> None:
    if IS_MAC:
        subprocess.run(
            ["bash", str(REPO_DIR / "install_launchd.sh"), "install"],
            check=True,
            cwd=str(REPO_DIR),
        )
        ok("Voice input service started")
        ok("Menu bar app started")
    else:
        launcher = _create_win_launcher()
        startup = (
            Path(os.environ.get("APPDATA", ""))
            / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        )
        startup.mkdir(parents=True, exist_ok=True)
        shutil.copy(launcher, startup / "voice-input.bat")
        ok("Autostart registered")


def _create_win_launcher() -> Path:
    launcher = REPO_DIR / "run-windows.bat"
    launcher.write_text(
        "@echo off\r\n"
        f'cd /d "{REPO_DIR}"\r\n'
        "if not exist .venv\\Scripts\\pythonw.exe (\r\n"
        "    echo venv not found, run install.command\r\n"
        "    pause & exit /b 1\r\n"
        ")\r\n"
        'start /b "" .venv\\Scripts\\pythonw.exe src\\main.py\r\n',
        encoding="utf-8",
    )
    return launcher


def generate_icon() -> None:
    """Windows only: draw microphone icon and save as multi-size ICO."""
    if not IS_WINDOWS:
        return
    script = r"""
from PIL import Image, ImageDraw
import sys, pathlib
sz = 64
img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.rounded_rectangle([20, 2, 44, 38], radius=10, fill=(0, 0, 0, 255))
draw.arc([14, 28, 50, 50], start=0, end=180, fill=(0, 0, 0, 255), width=4)
cx = sz // 2
draw.line([cx, 50, cx, 58], fill=(0, 0, 0, 255), width=4)
draw.line([cx - 10, 58, cx + 10, 58], fill=(0, 0, 0, 255), width=4)
sizes = [16, 32, 48, 64]
imgs = [img.resize((s, s), Image.LANCZOS) for s in sizes]
ico = pathlib.Path(sys.argv[1])
ico.parent.mkdir(parents=True, exist_ok=True)
imgs[0].save(str(ico), format="ICO", sizes=[(s, s) for s in sizes], append_images=imgs[1:])
"""
    ico_path = REPO_DIR / "assets" / "icon.ico"
    subprocess.run([str(VENV_PY), "-c", script, str(ico_path)], check=True)
    ok("Tray icon generated")


def open_permissions() -> None:
    """macOS only: open all three permission panes in System Settings."""
    if not IS_MAC:
        return
    print(f"\n  Find: {VENV_PY}")
    print("  Enable the toggle next to it in each panel.\n")
    for url in [
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    ]:
        subprocess.Popen(["open", url])
    ok("Microphone       — enable python3 toggle")
    ok("Input Monitoring — enable python3 toggle")
    ok("Accessibility    — enable python3 toggle")
    print()
    print("  Grant all three, then Voice Input is fully operational.")
    print("  You can also manage permissions later via the menu bar icon → Permissions.")


def launch_tray() -> None:
    """Windows only: start tray app (macOS relies on launchd)."""
    if not IS_WINDOWS:
        return
    subprocess.Popen([str(VENV_PYW), str(REPO_DIR / "src" / "main.py")], close_fds=True)
    ok("Voice Input launched in system tray")


def print_summary() -> None:
    print()
    print(f"{BOLD}── Done ─────────────────────────────────────────────{NC}")
    print()
    if IS_MAC:
        ok("Whisper large-v3 (Apple Silicon, mlx-whisper)")
        ok("launchd auto-start (voice input + menu bar)")
        print()
        print("  Look for the microphone icon in the top-right menu bar.")
        print("  Hotkey: Right Cmd (hold → release)  →  record speech  →  paste")
        print()
        print("  To stop:    ./install_launchd.sh stop")
        print("  To remove:  ./install_launchd.sh uninstall")
    else:
        ok("Whisper large-v3 (CPU, faster-whisper)")
        ok("Startup folder autostart")
        print()
        print("  Look for the microphone icon in the system tray (bottom-right).")
        print("  Hotkey: Right Ctrl (hold → release)  →  record speech  →  paste")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    step("Python environment")
    create_venv()

    step("Packages")
    install_packages()

    step("Whisper model")
    download_model()

    if IS_WINDOWS:
        step("Tray icon")
        generate_icon()

    step("Auto-start")
    setup_autostart()

    if IS_MAC:
        step("Permissions")
        open_permissions()

    if IS_WINDOWS:
        step("Launching")
        launch_tray()

    print_summary()


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        print(err, file=sys.stderr)
        try:
            (REPO_DIR / "install.log").write_text(err, encoding="utf-8")
        except Exception:
            pass
        sys.exit(1)
