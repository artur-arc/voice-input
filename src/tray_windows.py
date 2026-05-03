"""Windows system tray app for voice-input — mode, microphone, restart & update."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

_SRC_DIR: Final[Path] = Path(__file__).parent
_REPO_DIR: Final[Path] = _SRC_DIR.parent
sys.path.insert(0, str(_SRC_DIR))

from audio import AudioRecorder
from config import ConfigManager
from feedback import UserFeedback
from log_config import setup_logging
from modes import MODES, MIN_RECORD_SEC, SAMPLE_RATE
from paste_util import has_accessibility, paste_text
from transcription import Transcriber

logger = logging.getLogger(__name__)

_CONFIG_FILE: Final[Path] = _REPO_DIR / "voice-input-config.json"
_VERSION_FILE: Final[Path] = _REPO_DIR / "VERSION"
_ICON_FILE: Final[Path] = _REPO_DIR / "assets" / "icon.ico"

_WIN_PERM_URLS: dict[str, str] = {
    "Microphone": "ms-settings:privacy-microphone",
    "Keyboard hooks": "ms-settings:privacy-keyboard",
}

from pynput.keyboard import Key, Listener

RECORD_KEY: Key = Key.ctrl_r
MODE_KEY: Key = Key.alt_r


def _read_version(path: Path) -> str:
    try:
        return path.read_text().strip()
    except Exception:
        return "0.0.0"


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0,)


def _list_input_devices() -> list[tuple[int, str]]:
    """Return real input devices: deduplicated by name, no BT hands-free, no virtual devices."""
    try:
        import sounddevice as sd
        seen: set[str] = set()
        result: list[tuple[int, str]] = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] <= 0:
                continue
            name: str = d["name"].strip()
            if not name:
                continue
            # Skip Windows Bluetooth HFP (8 kHz hands-free — useless for transcription)
            if "bthhfenum.sys" in name.lower():
                continue
            # Skip Windows virtual/system devices
            if name in ("Переназначение звуковых устр. - Input", "Первичный драйвер записи звука",
                        "Primary Sound Capture Driver", "Stereo Mix"):
                continue
            if name in seen:
                continue
            seen.add(name)
            result.append((i, name))
        return result
    except Exception:
        logger.exception("Failed to query audio devices")
        return []


def _load_icon() -> Any:
    """Load icon.ico as PIL Image, or draw a microphone placeholder if missing."""
    from PIL import Image, ImageDraw
    if _ICON_FILE.exists():
        try:
            return Image.open(str(_ICON_FILE)).convert("RGBA")
        except Exception:
            pass
    # Fallback: draw a simple microphone silhouette
    sz = 64
    img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([20, 2, 44, 38], radius=10, fill=(0, 0, 0, 255))
    draw.arc([14, 28, 50, 50], start=0, end=180, fill=(0, 0, 0, 255), width=4)
    draw.line([sz // 2, 50, sz // 2, 58], fill=(0, 0, 0, 255), width=4)
    draw.line([sz // 2 - 10, 58, sz // 2 + 10, 58], fill=(0, 0, 0, 255), width=4)
    return img


class _WindowsUpdater:
    """Update via GitHub Releases (installer) or git-pull (cloned repo), then restart."""

    _GITHUB_API = "https://api.github.com/repos/artur-arc/voice-input/releases/latest"

    def __init__(self, repo: Path) -> None:
        self._repo = repo
        self._lock = threading.Lock()
        self._running = False

    def restart_and_update(
        self, callback: Callable[[str | None, str | None], None]
    ) -> bool:
        """Async restart+update. Returns False if already in progress."""
        with self._lock:
            if self._running:
                return False
            self._running = True
        threading.Thread(target=self._run, args=(callback,), daemon=True).start()
        return True

    def _run(self, callback: Callable[[str | None, str | None], None]) -> None:
        try:
            if (self._repo / ".git").exists():
                self._do_git(callback)
            else:
                self._do_github(callback)
        finally:
            with self._lock:
                self._running = False

    def _do_git(self, callback: Callable[[str | None, str | None], None]) -> None:
        repo = self._repo
        local_ver = _read_version(_VERSION_FILE)
        try:
            subprocess.run(
                ["git", "-C", str(repo), "fetch", "origin", "main"],
                check=True, capture_output=True, timeout=30,
            )
        except Exception as exc:
            logger.warning("git fetch failed: %s", exc)
            self._restart_process()
            callback(None, None)
            return
        try:
            remote_ver = subprocess.run(
                ["git", "-C", str(repo), "show", "origin/main:VERSION"],
                check=True, capture_output=True, text=True, timeout=10,
            ).stdout.strip()
        except Exception:
            remote_ver = local_ver
        has_update = _parse_version(remote_ver) > _parse_version(local_ver)
        if has_update:
            try:
                subprocess.run(
                    ["git", "-C", str(repo), "pull", "--ff-only", "origin", "main"],
                    check=True, capture_output=True, timeout=60,
                )
                venv_pip = repo / ".venv" / "Scripts" / "pip.exe"
                req = repo / "requirements-windows.txt"
                subprocess.run(
                    [str(venv_pip), "install", "-q", "-r", str(req)],
                    check=True, capture_output=True, timeout=120,
                )
            except subprocess.CalledProcessError as exc:
                err = exc.stderr.decode().strip() if exc.stderr else str(exc)
                self._restart_process()
                callback(err, None)
                return
        self._restart_process()
        callback(None, remote_ver if has_update else None)

    def _do_github(self, callback: Callable[[str | None, str | None], None]) -> None:
        import json
        import shutil
        import tempfile
        import urllib.request
        import zipfile

        local_ver = _read_version(_VERSION_FILE)

        try:
            req = urllib.request.Request(
                self._GITHUB_API,
                headers={"User-Agent": "voice-input-updater"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                release = json.loads(resp.read())
        except Exception as exc:
            logger.warning("GitHub API request failed: %s", exc)
            self._restart_process()
            callback(None, None)
            return

        tag = release.get("tag_name", "")
        remote_ver = tag.lstrip("v")
        has_update = _parse_version(remote_ver) > _parse_version(local_ver)

        if has_update:
            assets = release.get("assets", [])
            zip_url = next(
                (a["browser_download_url"] for a in assets if a["name"].endswith(".zip")),
                None,
            )
            if not zip_url:
                logger.warning("No zip asset in release %s", tag)
                self._restart_process()
                callback(f"No zip asset in release {tag}", None)
                return

            try:
                with tempfile.TemporaryDirectory() as tmp:
                    zip_path = Path(tmp) / "update.zip"
                    req = urllib.request.Request(
                        zip_url,
                        headers={"User-Agent": "voice-input-updater"},
                    )
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        zip_path.write_bytes(resp.read())
                    with zipfile.ZipFile(zip_path) as zf:
                        repo_resolved = self._repo.resolve()
                        for member in zf.namelist():
                            dest = (self._repo / member).resolve()
                            if not str(dest).startswith(str(repo_resolved)):
                                raise ValueError(f"Zip path traversal blocked: {member}")
                        zf.extractall(self._repo)
                venv_pip = self._repo / ".venv" / "Scripts" / "pip.exe"
                req_file = self._repo / "requirements-windows.txt"
                subprocess.run(
                    [str(venv_pip), "install", "-q", "-r", str(req_file)],
                    check=True, capture_output=True, timeout=120,
                )
            except Exception as exc:
                logger.error("Update failed: %s", exc)
                self._restart_process()
                callback(str(exc), None)
                return

        self._restart_process()
        callback(None, remote_ver if has_update else None)

    def _restart_process(self) -> None:
        try:
            # DETACHED_PROCESS: new process is independent of this one on Windows.
            # close_fds=True raises ValueError in pythonw.exe (no console handles).
            subprocess.Popen(
                [sys.executable] + sys.argv,
                creationflags=subprocess.DETACHED_PROCESS,
            )
        except Exception as exc:
            logger.warning("Process restart failed: %s", exc)
        os._exit(0)  # os._exit from a daemon thread; sys.exit does not propagate


class VoiceInputTray:
    """Windows system tray: language, microphone, permissions, version, restart, quit."""

    def __init__(
        self,
        config: ConfigManager,
        recorder: AudioRecorder,
        transcriber: Transcriber,
        feedback: UserFeedback,
        repo_dir: Path,
    ) -> None:
        import pystray
        self._pystray = pystray

        self._config = config
        self._recorder = recorder
        self._transcriber = transcriber
        self._feedback = feedback
        self._repo_dir = repo_dir
        self._updater = _WindowsUpdater(repo_dir)
        self._recording = False
        self._record_lock = threading.Lock()

        self._config.load()

        icon_image = _load_icon()
        mode = self._config.current_mode()
        self._icon = pystray.Icon(
            "VoiceInput",
            icon_image,
            title=f"Voice Input — {mode.label}",
            menu=self._build_menu(),
        )

    def run(self) -> None:
        """Start background threads then block on pystray main loop."""
        self._config.watch(self._on_config_changed)
        threading.Thread(target=self._warm_up, daemon=True).start()
        threading.Thread(target=self._run_listener, daemon=True).start()
        self._icon.run()

    # ── Transcription pipeline ────────────────────────────────────────────────

    def _warm_up(self) -> None:
        try:
            self._transcriber.warm_up()
        except Exception:
            logger.exception("Warm-up failed")

    def _run_listener(self) -> None:
        logger.info("Keyboard listener starting (RECORD_KEY=%r, MODE_KEY=%r)", RECORD_KEY, MODE_KEY)
        try:
            with Listener(on_press=self._on_press, on_release=self._on_release) as listener:
                logger.info("Keyboard listener active")
                listener.join()
        except Exception:
            logger.exception("Keyboard listener crashed")

    def _on_press(self, key: Any) -> None:
        logger.info("Key pressed: %r", key)
        if key == RECORD_KEY:
            logger.info("RECORD_KEY pressed — starting recording")
            with self._record_lock:
                if self._recording:
                    return
                self._recording = True
            self._recorder.start()
            self._feedback.play("Pop")

    def _on_release(self, key: Any) -> None:
        logger.info("Key released: %r", key)
        if key == RECORD_KEY:
            with self._record_lock:
                if not self._recording:
                    return
                self._recording = False
            logger.info("RECORD_KEY released — stopping recording")
            audio = self._recorder.stop()
            threading.Thread(
                target=self._transcribe_and_paste,
                args=(audio,),
                daemon=True,
            ).start()
        elif key == MODE_KEY:
            self._cycle_mode()

    def _transcribe_and_paste(self, audio: Any) -> None:
        try:
            mode = self._config.current_mode()
            text = self._transcriber.transcribe(audio, mode)
            if not text:
                self._feedback.play("Funk")
                return
            if has_accessibility():
                paste_text(text)
            else:
                try:
                    import pyperclip
                    pyperclip.copy(text)
                except Exception:
                    logger.warning("Clipboard copy failed — text lost")
            self._feedback.play("Tink")
            self._feedback.notify("Voice Input", text[:80])
        except Exception:
            logger.exception("Transcription/paste failed")
            self._feedback.play("Funk")

    def _cycle_mode(self) -> None:
        current = self._config.current_mode()
        idx = next((i for i, m in enumerate(MODES) if m.key == current.key), 0)
        new_idx = (idx + 1) % len(MODES)
        self._config.save(new_idx)
        mode = self._config.current_mode()
        self._icon.title = f"Voice Input — {mode.label}"
        self._icon.menu = self._build_menu()
        try:
            self._icon.update_menu()
        except Exception:
            pass

    # ── Menu ─────────────────────────────────────────────────────────────────

    def _build_menu(self) -> Any:
        pystray = self._pystray
        items: list[Any] = []
        local_ver = _read_version(_VERSION_FILE)
        devices = _list_input_devices()

        # Language modes (radio)
        # pystray 0.19.5 inspects ALL positional params (incl. defaults),
        # so lambdas with capture defaults (3 params) are rejected.
        # Wrap with an immediately-called outer lambda to produce a clean 2-param callable.
        # default=False prevents pystray from auto-activating the first item on left-click.
        for m in MODES:
            _key = m.key
            _label = m.label
            items.append(pystray.MenuItem(
                _label,
                (lambda k: lambda icon, item: self._on_mode(k))(_key),
                checked=(lambda k: lambda item: self._config.current_mode().key == k)(_key),
                radio=True,
                default=False,
            ))

        items.append(pystray.Menu.SEPARATOR)

        # Microphone devices (radio)
        items.append(pystray.MenuItem(
            "Auto-select",
            lambda icon, item: self._on_device(None),
            checked=lambda item: self._config.input_device() is None,
            radio=True,
            default=False,
        ))
        for _idx, name in devices:
            _n = name
            items.append(pystray.MenuItem(
                _n,
                (lambda n: lambda icon, item: self._on_device(n))(_n),
                checked=(lambda n: lambda item: self._config.input_device() == n)(_n),
                radio=True,
                default=False,
            ))

        items.append(pystray.Menu.SEPARATOR)

        # Permissions submenu (informational — opens Windows Settings)
        perm_items = [
            pystray.MenuItem(
                name,
                (lambda u: lambda icon, item: os.startfile(u))(url),
                default=False,
            )
            for name, url in _WIN_PERM_URLS.items()
        ]
        items.append(pystray.MenuItem("Permissions", pystray.Menu(*perm_items), default=False))

        items.append(pystray.Menu.SEPARATOR)

        items.append(pystray.MenuItem(f"Version {local_ver}", None, enabled=False))
        items.append(pystray.MenuItem("Restart to Update", self._on_restart_update, default=False))

        items.append(pystray.Menu.SEPARATOR)

        items.append(pystray.MenuItem("Uninstall…", self._on_uninstall, default=False))
        items.append(pystray.MenuItem("Quit", self._on_quit, default=False))

        return pystray.Menu(*items)

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_mode(self, key: str) -> None:
        for i, m in enumerate(MODES):
            if m.key == key:
                self._config.save(i)
                break
        mode = self._config.current_mode()
        self._icon.title = f"Voice Input — {mode.label}"
        self._icon.menu = self._build_menu()
        try:
            self._icon.update_menu()
        except Exception:
            pass

    def _on_device(self, name: str | None) -> None:
        self._config.save_device(name)
        self._icon.menu = self._build_menu()
        try:
            self._icon.update_menu()
        except Exception:
            pass

    def _on_config_changed(self, _index: int) -> None:
        mode = self._config.current_mode()
        self._icon.title = f"Voice Input — {mode.label}"
        self._icon.menu = self._build_menu()
        try:
            self._icon.update_menu()
        except Exception:
            pass

    def _on_restart_update(self, icon: Any, item: Any) -> None:
        self._updater.restart_and_update(
            lambda err, new_ver: self._on_restart_done(err, new_ver)
        )

    def _on_restart_done(self, error: str | None, new_ver: str | None) -> None:
        if error:
            logger.error("Restart/update failed: %s", error)
        elif new_ver:
            logger.info("Updated to v%s — restarting", new_ver)
        else:
            logger.info("Process restarted")

    def _on_uninstall(self, icon: Any, item: Any) -> None:
        import ctypes
        startup = (
            Path(os.environ.get("APPDATA", ""))
            / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        )
        bat = startup / "voice-input.bat"
        bat.unlink(missing_ok=True)
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Startup entry removed.\nTo fully uninstall, delete:\n{self._repo_dir}",
            "Voice Input Uninstalled",
            0x40,  # MB_ICONINFORMATION
        )
        icon.stop()

    def _on_quit(self, icon: Any, item: Any) -> None:
        logger.info("Quit requested via menu")
        icon.stop()


def main() -> None:
    import os as _os
    log_file = _REPO_DIR / "tray_windows.log"
    setup_logging(log_file)  # pythonw.exe has no stdout — always log to file
    logger.info("=== Windows tray starting (version %s, pid=%d) ===",
                _read_version(_VERSION_FILE), _os.getpid())
    try:
        config = ConfigManager(_CONFIG_FILE)
        VoiceInputTray(
            config=config,
            recorder=AudioRecorder(),
            transcriber=Transcriber(),  # uses large-v3 on Windows; MODEL_REPO is mlx-only
            feedback=UserFeedback(),
            repo_dir=_REPO_DIR,
        ).run()
        logger.info("=== Windows tray exited normally ===")
    except Exception:
        logger.exception("=== CRASH: unhandled exception in tray main ===")


if __name__ == "__main__":
    main()
