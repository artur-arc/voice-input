"""macOS menu bar app for voice-input — mode, microphone, restart & update."""
from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import rumps
import sounddevice as sd

_SRC_DIR: Final[Path] = Path(__file__).parent
_REPO_DIR: Final[Path] = _SRC_DIR.parent
sys.path.insert(0, str(_SRC_DIR))

from config import ConfigManager  # noqa: E402
from log_config import setup_logging  # noqa: E402
from modes import MODES  # noqa: E402

logger = logging.getLogger(__name__)

_CONFIG_FILE: Final[Path] = _REPO_DIR / "voice-input-config.json"
_VERSION_FILE: Final[Path] = _REPO_DIR / "VERSION"
_ICON_FILE: Final[Path] = _REPO_DIR / "assets" / "icon.svg"
_SERVICE_LABEL: Final[str] = "com.user.voice-input"
_MENU_LABEL: Final[str] = "com.user.voice-input-menu"


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


def _icon_is_loadable(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        from AppKit import NSImage  # type: ignore[import]
        img = NSImage.alloc().initByReferencingFile_(str(path))
        return img is not None and img.isValid()
    except Exception:
        return False


_PERM_URLS: dict[str, str] = {
    "Microphone": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
    "Input Monitoring": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
    "Accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
}


def _check_mic() -> bool:
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio  # type: ignore[import]
        # 0=NotDetermined, 1=Restricted, 2=Denied, 3=Authorized
        return int(AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)) == 3
    except Exception:
        return False


def _check_input_monitoring() -> bool:
    try:
        from Quartz import CGPreflightListenEventAccess  # type: ignore[import]
        return bool(CGPreflightListenEventAccess())
    except Exception:
        return False


def _check_accessibility() -> bool:
    try:
        from paste_util import has_accessibility  # noqa: PLC0415
        return has_accessibility()
    except Exception:
        return False


def _list_input_devices() -> list[tuple[int, str]]:
    try:
        return [
            (i, str(d["name"]))
            for i, d in enumerate(sd.query_devices())
            if d["max_input_channels"] > 0
        ]
    except Exception:
        logger.exception("Failed to query audio devices")
        return []


# ─────────────────────────────────────────────────────────────────────────────
class _Updater:
    """git fetch → version compare → optional pull → pip install → restart service."""

    def __init__(self, repo: Path) -> None:
        self._repo = repo
        self._lock = threading.Lock()
        self._running = False

    def restart_and_update(
        self,
        callback: Callable[[str | None, str | None], None],
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
            self._do(callback)
        finally:
            with self._lock:
                self._running = False

    def _do(self, callback: Callable[[str | None, str | None], None]) -> None:
        repo = self._repo
        local_ver = _read_version(_VERSION_FILE)

        # Fetch (best-effort — still restart if network is down)
        try:
            subprocess.run(
                ["git", "-C", str(repo), "fetch", "origin", "main"],
                check=True, capture_output=True, timeout=30,
            )
        except Exception as exc:
            logger.warning("git fetch failed: %s", exc)
            self._restart_service()
            callback(None, None)
            return

        # Read remote version
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
                venv_pip = repo / ".venv" / "bin" / "pip"
                req = repo / "requirements.txt"
                subprocess.run(
                    [str(venv_pip), "install", "-q", "-r", str(req)],
                    check=True, capture_output=True, timeout=120,
                )
            except subprocess.CalledProcessError as exc:
                err = exc.stderr.decode().strip() if exc.stderr else str(exc)
                self._restart_service()
                callback(err, None)
                return

        self._restart_service()
        callback(None, remote_ver if has_update else None)

    def _restart_service(self) -> None:
        uid = os.getuid()
        try:
            subprocess.run(
                ["launchctl", "kickstart", "-k", f"gui/{uid}/{_SERVICE_LABEL}"],
                capture_output=True, timeout=15,
            )
        except Exception as exc:
            logger.warning("Service restart failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
class VoiceInputMenuBar(rumps.App):
    """Status bar: language, microphone, version, restart-to-update, quit."""

    def __init__(self, config_file: Path, repo_dir: Path) -> None:
        has_icon = _icon_is_loadable(_ICON_FILE)
        super().__init__(
            name="VoiceInput",
            icon=str(_ICON_FILE) if has_icon else None,
            template=True,
            quit_button=None,
        )
        self._has_icon = has_icon
        self._repo_dir = repo_dir
        self._config = ConfigManager(config_file)
        self._updater = _Updater(repo_dir)
        self._main_q: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()

        self._config.load()
        self._config.watch(self._on_config_changed)
        self._refresh()

    # ── Main-thread dispatcher ────────────────────────────────────────────────

    @rumps.timer(0.5)
    def _drain(self, _: rumps.Timer) -> None:
        try:
            while True:
                self._main_q.get_nowait()()
        except queue.Empty:
            pass

    def _on_main(self, fn: Callable[[], None]) -> None:
        self._main_q.put(fn)

    # ── Menu ─────────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        mode = self._config.current_mode()
        configured_device = self._config.input_device()
        local_ver = _read_version(_VERSION_FILE)
        devices = _list_input_devices()

        self.title = mode.label if self._has_icon else f"🎙 {mode.label}"

        items: list[Any] = []

        # ── Language modes ────────────────────────────────────────────────────
        for i, m in enumerate(MODES):
            item = rumps.MenuItem(m.label, callback=self._on_mode)
            item.state = 1 if m.key == mode.key else 0
            items.append(item)

        items.append(None)

        # ── Microphone devices ────────────────────────────────────────────────
        auto = rumps.MenuItem("Auto-select", callback=self._on_device)
        auto.state = 1 if configured_device is None else 0
        items.append(auto)

        for _idx, name in devices:
            item = rumps.MenuItem(name, callback=self._on_device)
            item.state = 1 if name == configured_device else 0
            items.append(item)

        items.append(None)

        # ── Permissions ───────────────────────────────────────────────────────
        items.append(self._build_permissions_menu())

        items.append(None)

        # ── Version + Restart to Update ───────────────────────────────────────
        ver_item = rumps.MenuItem(f"Version {local_ver}")
        items.append(ver_item)
        items.append(rumps.MenuItem("Restart to Update", callback=self._on_restart_update))

        items.append(None)
        items.append(rumps.MenuItem("Uninstall…", callback=self._on_uninstall))
        items.append(rumps.MenuItem("Quit", callback=rumps.quit_application))

        self.menu.clear()
        self.menu = items

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_mode(self, sender: rumps.MenuItem) -> None:
        for i, m in enumerate(MODES):
            if m.label == sender.title:
                self._config.save(i)
                break
        self._refresh()

    def _on_device(self, sender: rumps.MenuItem) -> None:
        name = None if sender.title == "Auto-select" else sender.title
        self._config.save_device(name)
        self._refresh()

    def _on_config_changed(self, _index: int) -> None:
        self._on_main(self._refresh)

    def _on_restart_update(self, sender: rumps.MenuItem) -> None:
        sender.title = "Working…"
        started = self._updater.restart_and_update(
            lambda err, new_ver: self._on_main(
                lambda: self._on_restart_done(err, new_ver)
            )
        )
        if not started:
            self._refresh()

    def _build_permissions_menu(self) -> rumps.MenuItem:
        checks = {
            "Microphone": _check_mic(),
            "Input Monitoring": _check_input_monitoring(),
            "Accessibility": _check_accessibility(),
        }
        python_path = str(self._repo_dir / ".venv" / "bin" / "python3")
        python_display = python_path.replace(str(Path.home()), "~")
        parent = rumps.MenuItem("Permissions")
        # Informational header — shows which binary needs the permissions
        parent["__hint__"] = rumps.MenuItem(f"Grant to: {python_display}")
        parent["__sep__"] = rumps.MenuItem("─────────────────")
        for name, granted in checks.items():
            url = _PERM_URLS[name]
            item = rumps.MenuItem(name, callback=lambda _, u=url: subprocess.Popen(["open", u]))
            item.state = 1 if granted else 0
            parent[name] = item
        return parent

    def _on_uninstall(self, _: rumps.MenuItem) -> None:
        response = rumps.alert(
            title="Uninstall Voice Input?",
            message=(
                "This will stop the service, remove it from login items, "
                f"and delete {self._repo_dir}."
            ),
            ok="Uninstall",
            cancel="Cancel",
        )
        if response != 1:
            return
        try:
            subprocess.run(
                ["bash", str(self._repo_dir / "install_launchd.sh"), "uninstall"],
                check=True, timeout=15,
            )
        except Exception as exc:
            rumps.alert(title="Uninstall failed", message=str(exc), ok="OK")
            return
        # Schedule folder deletion after this process exits (can't delete our own cwd)
        subprocess.Popen(
            ["bash", "-c", f'sleep 2 && rm -rf "{self._repo_dir}"'],
            start_new_session=True,
        )
        rumps.quit_application()

    def _on_restart_done(self, error: str | None, new_ver: str | None) -> None:
        if error:
            logger.error("Restart/update failed: %s", error)
            self._refresh()
        elif new_ver:
            logger.info("Updated to v%s — restarting menu bar", new_ver)
            rumps.quit_application()  # launchd KeepAlive restarts us with new code
        else:
            logger.info("Service restarted")
            self._refresh()


# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    log_file = _REPO_DIR / "menu_bar.log"
    setup_logging(log_file if sys.stdout.isatty() else None)
    logger.info("Menu bar starting (version %s)", _read_version(_VERSION_FILE))
    icon_ok = _icon_is_loadable(_ICON_FILE)
    logger.info("Icon: %s (%s)", _ICON_FILE.name, "loaded" if icon_ok else "not available")
    VoiceInputMenuBar(config_file=_CONFIG_FILE, repo_dir=_REPO_DIR).run()


if __name__ == "__main__":
    main()
