#!/usr/bin/env python3
"""Windows installer: venv, packages, model download, icon, autostart, launch."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_DIR: Path = Path(__file__).parent
VENV_DIR: Path = REPO_DIR / ".venv"
VENV_PY: Path = VENV_DIR / "Scripts" / "python.exe"
VENV_PYW: Path = VENV_DIR / "Scripts" / "pythonw.exe"
VENV_PIP: Path = VENV_DIR / "Scripts" / "pip.exe"
REQUIREMENTS: Path = REPO_DIR / "requirements-windows.txt"
MODEL_NAME: str = "large-v3"

BOLD = "\033[1m"
GREEN = "\033[0;32m"
NC = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{NC} {msg}")


def step(msg: str) -> None:
    print(f"\n{BOLD}── {msg}{NC}")


def check_python_version() -> None:
    if sys.version_info < (3, 11):
        print(f"  Python 3.11+ required, found {sys.version_info.major}.{sys.version_info.minor}")
        sys.exit(1)
    ok(f"Python {sys.version_info.major}.{sys.version_info.minor}")


def create_venv() -> None:
    if VENV_DIR.exists() and not VENV_PY.exists():
        shutil.rmtree(VENV_DIR)
    if not VENV_DIR.exists():
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    ok("Virtual environment ready")


def install_packages() -> None:
    subprocess.run(
        [str(VENV_PIP), "install", "--quiet", "--upgrade", "pip"],
        check=True,
    )
    subprocess.run(
        [str(VENV_PIP), "install", "--quiet", "-r", str(REQUIREMENTS)],
        check=True,
    )
    ok("All packages installed")


def download_model() -> None:
    print("  Downloading faster-whisper large-v3 (~1.5 GB) — this takes a few minutes...")
    script = (
        "from faster_whisper import WhisperModel; "
        "import numpy as np; "
        f"m = WhisperModel('{MODEL_NAME}', device='cpu', compute_type='int8'); "
        "segs, _ = m.transcribe(np.zeros(16000, dtype='float32'), language='en'); "
        "list(segs); print('  Model ready.')"
    )
    subprocess.run([str(VENV_PY), "-c", script], check=True)
    ok("Model downloaded and warmed up")


def generate_icon() -> None:
    """Draw microphone icon using PIL.ImageDraw (no cairosvg needed)."""
    script = r"""
from PIL import Image, ImageDraw
import sys, pathlib

sz = 64
img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Microphone body
draw.rounded_rectangle([20, 2, 44, 38], radius=10, fill=(0, 0, 0, 255))

# Stand arc
draw.arc([14, 28, 50, 50], start=0, end=180, fill=(0, 0, 0, 255), width=4)

# Stand line and base
cx = sz // 2
draw.line([cx, 50, cx, 58], fill=(0, 0, 0, 255), width=4)
draw.line([cx - 10, 58, cx + 10, 58], fill=(0, 0, 0, 255), width=4)

sizes = [16, 32, 48, 64]
imgs = [img.resize((s, s), Image.LANCZOS) for s in sizes]

ico_path = pathlib.Path(sys.argv[1])
ico_path.parent.mkdir(parents=True, exist_ok=True)
imgs[0].save(
    str(ico_path),
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=imgs[1:],
)
print(f"  Icon saved: {ico_path}")
"""
    ico_path = REPO_DIR / "assets" / "icon.ico"
    subprocess.run([str(VENV_PY), "-c", script, str(ico_path)], check=True)
    ok(f"Icon generated: assets/icon.ico")


def create_launcher() -> Path:
    launcher = REPO_DIR / "run-windows.bat"
    launcher.write_text(
        "@echo off\r\n"
        f'cd /d "{REPO_DIR}"\r\n'
        "if not exist .venv\\Scripts\\pythonw.exe (\r\n"
        "    echo venv not found, run install.bat\r\n"
        "    pause\r\n"
        "    exit /b 1\r\n"
        ")\r\n"
        'start /b "" .venv\\Scripts\\pythonw.exe src\\main.py\r\n',
        encoding="utf-8",
    )
    return launcher


def register_autostart() -> None:
    launcher = create_launcher()
    startup = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    )
    startup.mkdir(parents=True, exist_ok=True)
    dest = startup / "voice-input.bat"
    shutil.copy(launcher, dest)
    ok(f"Autostart registered")


def launch_tray() -> None:
    subprocess.Popen(
        [str(VENV_PYW), str(REPO_DIR / "src" / "main.py")],
        close_fds=True,
    )
    ok("Voice Input launched in system tray")


def main() -> None:
    print()
    print("╔" + "═" * 38 + "╗")
    print("║    Voice Input — Windows Installer   ║")
    print("╚" + "═" * 38 + "╝")
    print()
    print("  This will take a few minutes. Do not close this window.")
    print()

    step("Checking Python version")
    check_python_version()

    step("Creating virtual environment")
    create_venv()

    step("Installing packages")
    install_packages()

    step("Downloading Whisper large-v3 model (~1.5 GB)")
    download_model()

    step("Generating tray icon")
    generate_icon()

    step("Registering autostart")
    register_autostart()

    step("Launching Voice Input")
    launch_tray()

    print()
    print("─" * 50)
    print()
    ok("Voice Input is running in the system tray (bottom-right).")
    print()
    print("  Hotkey: Right Ctrl (hold → release) to record speech.")
    print("  Click the tray icon to switch language or microphone.")
    print()
    input("Press Enter to close this window...")


if __name__ == "__main__":
    main()
