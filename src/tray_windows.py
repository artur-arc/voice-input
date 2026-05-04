"""Windows system tray app for voice-input — mode, microphone, restart & update."""
from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import tempfile
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

_GITHUB_URL: Final[str] = "https://github.com/artur-arc/voice-input"

_WIN_PERM_URLS: dict[str, str] = {
    "Microphone": "ms-settings:privacy-microphone",
    "Keyboard hooks": "ms-settings:privacy-keyboard",
}

_MODEL_LABELS: dict[str, str] = {
    "large-v3-q5_0": "Large (1.1 GB)",
    "medium-q5_0":   "Medium (514 MB)",
    "tiny":          "Tiny (75 MB)",
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
    from PIL import Image, ImageDraw  # type: ignore[import]
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
                            if not dest.is_relative_to(repo_resolved):
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
        global _mutex_handle
        # Release the mutex before spawning the new process so it can acquire it
        # immediately without hitting ERROR_ALREADY_EXISTS.
        if _mutex_handle:
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = 0
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
        import pystray  # type: ignore[import]
        self._pystray = pystray

        self._config = config
        self._recorder = recorder
        self._transcriber = transcriber
        self._feedback = feedback
        self._repo_dir = repo_dir
        self._updater = _WindowsUpdater(repo_dir)
        self._recording = False
        self._record_lock = threading.Lock()
        self._loading_notified = False  # show "waiting for model" only once

        self._config.load()
        self._feedback.sounds_enabled = self._config.sounds_enabled()
        self._feedback.notifications_enabled = self._config.notifications_enabled()

        icon_image = _load_icon()
        mode = self._config.current_mode()
        self._icon = pystray.Icon(
            "VoiceInput",
            icon_image,
            title=f"Voice Input — {mode.label}",
            menu=self._build_menu(),
        )
        if hasattr(self._feedback, "set_notify_icon"):
            self._feedback.set_notify_icon(self._icon)

    def run(self) -> None:
        """Start background threads then block on pystray main loop."""
        self._config.watch(self._on_config_changed)
        threading.Thread(target=self._warm_up, daemon=True).start()
        threading.Thread(target=self._run_listener, daemon=True).start()
        self._icon.run()

    # ── Transcription pipeline ────────────────────────────────────────────────

    def _warm_up(self) -> None:
        try:
            self._icon.title = "Voice Input — loading model…"
            self._transcriber.warm_up()
            if self._transcriber.is_ready() and getattr(self._transcriber, "_load_error", None) is None:
                self._loading_notified = False
                mode = self._config.current_mode()
                self._icon.title = f"Voice Input — {mode.label}"
                self._feedback.play("Pop")
                self._feedback.notify("Voice Input", "Model ready — voice input active")
                logger.info("Model ready — tray notified user")
            else:
                self._icon.title = "Voice Input — model failed"
                err = getattr(self._transcriber, "_load_error", "unknown error")
                self._feedback.notify("Voice Input", f"Model failed to load: {err}")
                logger.error("Model not ready after warm_up: %s", err)
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
            try:
                self._recorder.start(preferred_name=self._config.input_device())
                self._feedback.play("Pop")
            except RuntimeError as exc:
                logger.error("Microphone start failed: %s", exc)
                with self._record_lock:
                    self._recording = False
                self._feedback.notify(
                    "Voice Input",
                    "Microphone error — check permissions or device",
                )

    def _on_release(self, key: Any) -> None:
        logger.info("Key released: %r", key)
        if key == RECORD_KEY:
            with self._record_lock:
                if not self._recording:
                    return
                self._recording = False
            logger.info("RECORD_KEY released — stopping recording")
            active_hwnd = ctypes.windll.user32.GetForegroundWindow()
            audio = self._recorder.stop()
            if len(audio) < SAMPLE_RATE * MIN_RECORD_SEC:
                return
            threading.Thread(
                target=self._transcribe_and_paste,
                args=(audio, active_hwnd),
                daemon=True,
            ).start()
        elif key == MODE_KEY:
            self._cycle_mode()

    def _transcribe_and_paste(self, audio: Any, target_hwnd: int = 0) -> None:
        try:
            mode = self._config.current_mode()
            if not self._transcriber.is_ready() and not self._loading_notified:
                self._loading_notified = True
                self._feedback.notify("Voice Input", "Recording saved — waiting for model to load…")
            text = self._transcriber.transcribe(audio, mode)
            if not text:
                self._feedback.play("Funk")
                return
            if has_accessibility():
                paste_text(text, target_hwnd)
            else:
                try:
                    import pyperclip
                    pyperclip.copy(text)
                except Exception:
                    logger.warning("Clipboard copy failed — text lost")
            self._feedback.play("Tink")
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

        # Microphone devices (submenu with radio)
        mic_items: list[Any] = [
            pystray.MenuItem(
                "Auto-select",
                lambda icon, item: self._on_device(None),
                checked=lambda item: self._config.input_device() is None,
                radio=True,
                default=False,
            )
        ]
        for _idx, name in devices:
            _n = name
            mic_items.append(pystray.MenuItem(
                _n,
                (lambda n: lambda icon, item: self._on_device(n))(_n),
                checked=(lambda n: lambda item: self._config.input_device() == n)(_n),
                radio=True,
                default=False,
            ))
        items.append(pystray.MenuItem("Microphone", pystray.Menu(*mic_items), default=False))

        # Model selector (radio) — only shown when multiple models are on disk
        available_models = self._transcriber.available_models()
        if len(available_models) > 1:
            model_items: list[Any] = []
            for _m in available_models:
                _label = _MODEL_LABELS.get(_m, _m)
                model_items.append(pystray.MenuItem(
                    _label,
                    (lambda m: lambda icon, item: self._on_model(m))(_m),
                    checked=(lambda m: lambda item: self._transcriber.model_repo == m)(_m),
                    radio=True,
                    default=False,
                ))
            items.append(pystray.MenuItem("Model", pystray.Menu(*model_items), default=False))
        else:
            model_name = self._transcriber.model_repo
            items.append(pystray.MenuItem(
                "Model",
                pystray.Menu(pystray.MenuItem(
                    _MODEL_LABELS.get(model_name, model_name), None, enabled=False
                )),
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

        settings_items = [
            pystray.MenuItem(
                "Sound Effects",
                lambda *_: self._on_toggle_sounds(),
                checked=lambda _: self._config.sounds_enabled(),
                default=False,
            ),
            pystray.MenuItem(
                "Notifications",
                lambda *_: self._on_toggle_notifications(),
                checked=lambda _: self._config.notifications_enabled(),
                default=False,
            ),
        ]
        items.append(pystray.MenuItem("Settings", pystray.Menu(*settings_items), default=False))

        items.append(pystray.Menu.SEPARATOR)

        items.append(pystray.MenuItem(
            f"Version {local_ver}",
            lambda *_: os.startfile(_GITHUB_URL),
            default=False,
        ))
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

    def _on_model(self, name: str) -> None:
        if self._transcriber.model_repo == name:
            return
        self._config.save_model_name(name)
        self._transcriber.switch_model(name)
        self._icon.menu = self._build_menu()
        try:
            self._icon.update_menu()
        except Exception:
            pass
        threading.Thread(target=self._warm_up, daemon=True).start()

    def _on_model_fallback(self, from_model: str, to_model: str) -> None:
        from_label = _MODEL_LABELS.get(from_model, from_model)
        to_label = _MODEL_LABELS.get(to_model, to_model)
        logger.warning("Auto-fallback: %s → %s", from_model, to_model)
        self._config.save_model_name(to_model)
        self._feedback.notify(
            "Voice Input — Model Switch",
            f"{from_label} was too slow — switched to {to_label}",
        )
        self._icon.menu = self._build_menu()
        try:
            self._icon.update_menu()
        except Exception:
            pass

    def _on_toggle_sounds(self) -> None:
        enabled = not self._config.sounds_enabled()
        self._config.save_sounds_enabled(enabled)
        self._feedback.sounds_enabled = enabled
        self._icon.menu = self._build_menu()
        try:
            self._icon.update_menu()
        except Exception:
            pass

    def _on_toggle_notifications(self) -> None:
        enabled = not self._config.notifications_enabled()
        self._config.save_notifications_enabled(enabled)
        self._feedback.notifications_enabled = enabled
        self._icon.menu = self._build_menu()
        try:
            self._icon.update_menu()
        except Exception:
            pass

    def _on_config_changed(self, _index: int) -> None:
        self._feedback.sounds_enabled = self._config.sounds_enabled()
        self._feedback.notifications_enabled = self._config.notifications_enabled()
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
        models_dir = self._repo_dir / "models"
        model_size_mb = 0.0
        if models_dir.exists():
            model_size_mb = sum(
                f.stat().st_size for f in models_dir.glob("*.bin") if f.is_file()
            ) / 1_048_576
        model_info = f"\n• Whisper model cache ({model_size_mb:.0f} MB)" if model_size_mb > 0 else ""

        confirmed = ctypes.windll.user32.MessageBoxW(
            0,
            f"This will permanently remove:\n"
            f"• Startup entry"
            f"{model_info}"
            f"\n• App folder: {self._repo_dir}\n\n"
            f"Continue?",
            "Uninstall Voice Input",
            0x04 | 0x30,  # MB_YESNO | MB_ICONWARNING
        )
        if confirmed != 6:  # IDYES
            return

        # Remove startup entry
        startup = (
            Path(os.environ.get("APPDATA", ""))
            / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        )
        (startup / "voice-input.bat").unlink(missing_ok=True)

        # Terminate the worker subprocess so it releases the model .bin file lock.
        # Windows does not kill child processes automatically when the parent exits,
        # so rmdir /s /q would fail to delete an open .bin file without this.
        self._transcriber.shutdown()

        # Delete the app folder after the tray process exits via a detached batch script.
        # Extra 2-second wait after PID disappears lets OS release any remaining file handles.
        # Retry loop (up to 5 attempts) handles transient locks from the dying venv.
        pid = os.getpid()
        fd, tmp_path = tempfile.mkstemp(suffix=".bat", prefix="vi_uninstall_")
        os.close(fd)
        # Repo path passed via env var (VI_REPO) — avoids cmd.exe OEM codepage
        # mangling of non-ASCII characters (e.g. Cyrillic usernames) in the bat body.
        Path(tmp_path).write_text(
            "@echo off\n"
            ":wait\n"
            f"tasklist /fi \"PID eq {pid}\" 2>nul | find \"{pid}\" >nul\n"
            "if not errorlevel 1 (timeout /t 1 /nobreak >nul & goto wait)\n"
            "timeout /t 2 /nobreak >nul\n"
            "set retries=5\n"
            ":retry\n"
            "rmdir /s /q \"%VI_REPO%\" 2>nul\n"
            "if not exist \"%VI_REPO%\" goto done\n"
            "set /a retries-=1\n"
            "if %retries% gtr 0 (timeout /t 2 /nobreak >nul & goto retry)\n"
            ":done\n"
            "del \"%~f0\"\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["VI_REPO"] = str(self._repo_dir)
        subprocess.Popen(
            ["cmd.exe", "/c", tmp_path],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            env=env,
        )
        icon.stop()

    def _on_quit(self, icon: Any, item: Any) -> None:
        logger.info("Quit requested via menu")
        self._transcriber.shutdown()
        icon.stop()


_mutex_handle: int = 0


def _acquire_single_instance_lock() -> bool:
    """Return True if this is the only running instance (Windows named mutex)."""
    global _mutex_handle
    _MUTEX_NAME = "Global\\VoiceInputTrayApp"
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return False
    _mutex_handle = handle
    return True


def main() -> None:
    import os as _os
    log_file = _REPO_DIR / "tray_windows.log"
    setup_logging(log_file)  # pythonw.exe has no stdout — always log to file

    if not _acquire_single_instance_lock():
        logger.warning("Another instance is already running — exiting (pid=%d)", _os.getpid())
        return

    logger.info("=== Windows tray starting (version %s, pid=%d) ===",
                _read_version(_VERSION_FILE), _os.getpid())
    try:
        config = ConfigManager(_CONFIG_FILE)
        config.load()
        saved_model = config.model_name()

        # on_fallback is wired after tray creation — use a mutable cell for late binding
        tray_cell: list[VoiceInputTray] = []

        def _on_fallback(from_m: str, to_m: str) -> None:
            if tray_cell:
                tray_cell[0]._on_model_fallback(from_m, to_m)

        transcriber = Transcriber(initial_model=saved_model, on_fallback=_on_fallback)
        tray = VoiceInputTray(
            config=config,
            recorder=AudioRecorder(),
            transcriber=transcriber,
            feedback=UserFeedback(),
            repo_dir=_REPO_DIR,
        )
        tray_cell.append(tray)
        tray.run()
        logger.info("=== Windows tray exited normally ===")
    except Exception:
        logger.exception("=== CRASH: unhandled exception in tray main ===")


if __name__ == "__main__":
    main()
