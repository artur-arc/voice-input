#!/usr/bin/env python3
"""Cross-platform setup for voice-input — macOS and Windows from one script.

Called by install.command (macOS / Windows Git Bash) after Python is confirmed available.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
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


def _detect_win_model() -> str:
    """Choose faster-whisper model based on total physical RAM (no extra dependencies)."""
    import ctypes

    class _MemStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength",                ctypes.c_ulong),
            ("dwMemoryLoad",            ctypes.c_ulong),
            ("ullTotalPhys",            ctypes.c_ulonglong),
            ("ullAvailPhys",            ctypes.c_ulonglong),
            ("ullTotalPageFile",        ctypes.c_ulonglong),
            ("ullAvailPageFile",        ctypes.c_ulonglong),
            ("ullTotalVirtual",         ctypes.c_ulonglong),
            ("ullAvailVirtual",         ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    try:
        mem = _MemStatus()
        mem.dwLength = ctypes.sizeof(mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))  # type: ignore[attr-defined]
        total_gb = mem.ullTotalPhys / (1024 ** 3)
    except Exception:
        total_gb = 0.0

    if total_gb >= 14:
        return "large-v3-q5_0"  # GGML q5_0 ~1.1 GB
    elif total_gb >= 4:
        return "medium-q5_0"    # GGML q5_0 ~514 MB
    else:
        return "tiny"           # GGML ~75 MB — RAM detection failed or genuinely low



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
    key_pkg = "pywhispercpp" if IS_WINDOWS else "mlx-whisper"
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
    label = "pywhispercpp is ~20 MB" if IS_WINDOWS else "mlx-whisper is ~300 MB"
    print(f"  Installing packages ({label} — please wait)...")
    subprocess.run(
        [str(VENV_PY), "-m", "pip", "install", "--upgrade", "--progress-bar", "on",
         "-r", str(REQUIREMENTS)],
        check=True,
    )
    ok("All packages installed")


def download_model() -> None:
    env = os.environ.copy()
    env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    # Allow hf-xet (fast XET protocol) — removing DISABLE_IMPLICIT_TOKEN lets it activate

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
        target = _detect_win_model()
        models_dir = REPO_DIR / "models"
        models_dir.mkdir(parents=True, exist_ok=True)

        sizes = {
            "tiny":           "~75 MB",
            "medium-q5_0":    "~514 MB",
            "large-v3-q5_0":  "~1.1 GB",
        }

        # Always download tiny as CPU-speed fallback; then download primary if different.
        to_download = ["tiny"] if target == "tiny" else ["tiny", target]
        for model_name in to_download:
            model_file = models_dir / f"ggml-{model_name}.bin"
            if model_file.exists() and model_file.stat().st_size > 1_000_000:
                size_mb = model_file.stat().st_size / 1_048_576
                ok(f"ggml-{model_name}.bin already cached ({size_mb:.0f} MB)")
                continue
            label = sizes.get(model_name, "?")
            print(f"  Downloading ggml-{model_name}.bin ({label})...")
            url = (
                f"https://huggingface.co/ggerganov/whisper.cpp"
                f"/resolve/main/ggml-{model_name}.bin"
            )
            tmp_file = model_file.with_suffix(".tmp")

            def _progress(count: int, block: int, total: int) -> None:
                if total > 0:
                    pct = min(100, count * block * 100 // total)
                    print(f"\r  {pct}%", end="", flush=True)

            try:
                urllib.request.urlretrieve(url, str(tmp_file), reporthook=_progress)
                print()
                tmp_file.rename(model_file)
            except Exception:
                tmp_file.unlink(missing_ok=True)
                raise

    ok("Model ready")


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
        'cd /d "%~dp0"\r\n'  # relative to the bat file — survives folder moves
        "if not exist .venv\\Scripts\\pythonw.exe (\r\n"
        "    echo venv not found, run install.bat\r\n"
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
    # Kill any existing tray instance so the fresh one can acquire the mutex.
    # (setup.py may run while the app is already running — e.g. after a model re-download)
    subprocess.run(
        ["taskkill", "/f", "/im", "pythonw.exe"],
        capture_output=True,
    )
    import time as _time; _time.sleep(1)
    subprocess.Popen(
        [str(VENV_PYW), str(REPO_DIR / "src" / "main.py")],
        creationflags=subprocess.DETACHED_PROCESS,
    )
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
        model = _detect_win_model()
        model_display = model.split("-q")[0]  # "medium" from "medium-q5_0"
        ok(f"Whisper {model_display} quantized (CPU, whisper.cpp) + tiny fallback")
        ok("Startup folder autostart")
        print()
        print("  Look for the microphone icon in the system tray (bottom-right).")
        print("  Hotkey: Right Ctrl (hold → release)  →  record speech  →  paste")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if IS_WINDOWS:
        # Kill any running tray instance before touching venv or model files.
        # A live pythonw.exe locks .pyd files in .venv, causing shutil.rmtree to fail.
        subprocess.run(["taskkill", "/f", "/im", "pythonw.exe"], capture_output=True)
        import time as _time; _time.sleep(1)

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
