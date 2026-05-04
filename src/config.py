import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from modes import MODES, Mode

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, config_file: Path) -> None:
        self._config_file = config_file
        self._lock = threading.Lock()
        self._mode_index: int = 2
        self._input_device: str | None = None
        self._sounds_enabled: bool = True
        self._notifications_enabled: bool = True
        self._watch_thread: threading.Thread | None = None

    def load(self) -> None:
        try:
            raw: dict[str, Any] = json.loads(self._config_file.read_text())
            vcfg: dict[str, Any] = raw.get("voiceInputConfig", raw)

            new_mode_index = self._mode_index
            for i, m in enumerate(MODES):
                if vcfg.get(m.key) is True:
                    new_mode_index = i
                    break

            # input_device lives at top level (outside voiceInputConfig)
            new_input_device = raw.get("input_device") if "voiceInputConfig" in raw else None

            new_sounds = bool(raw.get("sounds_enabled", True))
            new_notifications = bool(raw.get("notifications_enabled", True))

            with self._lock:
                self._mode_index = new_mode_index
                self._input_device = new_input_device
                self._sounds_enabled = new_sounds
                self._notifications_enabled = new_notifications
        except Exception:
            logger.exception("Config load error")

    def save(self, index: int) -> None:
        try:
            raw: dict[str, Any] = json.loads(self._config_file.read_text())
        except Exception:
            raw = {}
        vcfg = raw.get("voiceInputConfig", raw)
        for i, m in enumerate(MODES):
            vcfg[m.key] = (i == index)
        if "voiceInputConfig" in raw:
            raw["voiceInputConfig"] = vcfg
        else:
            raw = vcfg
        self._config_file.write_text(json.dumps(raw, indent=4))
        with self._lock:
            self._mode_index = index

    def current_mode(self) -> Mode:
        with self._lock:
            return MODES[self._mode_index]

    def input_device(self) -> str | None:
        with self._lock:
            return self._input_device

    def save_device(self, name: str | None) -> None:
        try:
            raw: dict[str, Any] = json.loads(self._config_file.read_text())
        except Exception:
            raw = {}
        raw["input_device"] = name
        self._config_file.write_text(json.dumps(raw, indent=4))
        with self._lock:
            self._input_device = name

    def sounds_enabled(self) -> bool:
        with self._lock:
            return self._sounds_enabled

    def notifications_enabled(self) -> bool:
        with self._lock:
            return self._notifications_enabled

    def save_sounds_enabled(self, enabled: bool) -> None:
        try:
            raw: dict[str, Any] = json.loads(self._config_file.read_text())
        except Exception:
            raw = {}
        raw["sounds_enabled"] = enabled
        self._config_file.write_text(json.dumps(raw, indent=4))
        with self._lock:
            self._sounds_enabled = enabled

    def save_notifications_enabled(self, enabled: bool) -> None:
        try:
            raw: dict[str, Any] = json.loads(self._config_file.read_text())
        except Exception:
            raw = {}
        raw["notifications_enabled"] = enabled
        self._config_file.write_text(json.dumps(raw, indent=4))
        with self._lock:
            self._notifications_enabled = enabled

    def watch(self, on_change: Callable[[int], None]) -> None:
        if self._watch_thread is not None:
            return
        self._watch_thread = threading.Thread(
            target=self._watch_loop,
            args=(on_change,),
            daemon=True,
        )
        self._watch_thread.start()

    def _watch_loop(self, on_change: Callable[[int], None]) -> None:
        try:
            last_mtime = self._config_file.stat().st_mtime
        except Exception:
            last_mtime = 0.0
        while True:
            time.sleep(2)
            try:
                mtime = self._config_file.stat().st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    self.load()
                    with self._lock:
                        idx = self._mode_index
                    on_change(idx)
            except Exception:
                logger.exception("Config watch error")
