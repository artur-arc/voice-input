import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from modes import LANG_TO_CMD, MODES, TEXT_MODES, Mode

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, config_file: Path) -> None:
        self._config_file = config_file
        self._lock = threading.Lock()
        self._mode_index: int = 1          # index into TEXT_MODES
        self._input_device: str | None = None
        self._sounds_enabled: bool = True
        self._notifications_enabled: bool = True
        self._model_name: str | None = None
        self._command_lang: str = "auto"   # "auto" | "ru" | "en" | "he"
        self._commands_enabled: bool = False
        self._watch_thread: threading.Thread | None = None

    def load(self) -> None:
        try:
            raw: dict[str, Any] = json.loads(self._config_file.read_text())

            # New format: "languages" section; legacy fallback: "voiceInputConfig"
            lang_cfg: dict[str, Any] = raw.get("languages") or raw.get("voiceInputConfig", raw)

            new_mode_index = self._mode_index
            for i, m in enumerate(TEXT_MODES):
                if lang_cfg.get(m.key) is True:
                    new_mode_index = i
                    break

            new_input_device = raw.get("input_device")
            new_sounds = bool(raw.get("sounds_enabled", True))
            new_notifications = bool(raw.get("notifications_enabled", True))
            new_model = raw.get("selected_model") or None
            new_cmd_lang = raw.get("commands", {}).get("language", "auto")
            new_commands_enabled = bool(raw.get("commands_enabled", False))

            with self._lock:
                self._mode_index = new_mode_index
                self._input_device = new_input_device
                self._sounds_enabled = new_sounds
                self._notifications_enabled = new_notifications
                self._model_name = new_model
                self._command_lang = new_cmd_lang
                self._commands_enabled = new_commands_enabled
        except Exception:
            logger.exception("Config load error")

    def save(self, index: int) -> None:
        try:
            raw: dict[str, Any] = json.loads(self._config_file.read_text())
        except Exception:
            raw = {}
        # Always write new format; drop legacy voiceInputConfig key
        raw.pop("voiceInputConfig", None)
        lang_cfg: dict[str, bool] = {}
        for i, m in enumerate(TEXT_MODES):
            lang_cfg[m.key] = (i == index)
        raw["languages"] = lang_cfg
        self._config_file.write_text(json.dumps(raw, indent=4))
        with self._lock:
            self._mode_index = index

    def current_mode(self) -> Mode:
        with self._lock:
            return TEXT_MODES[self._mode_index]

    def command_mode(self) -> Mode:
        """Return the command Mode based on language setting (auto or explicit)."""
        with self._lock:
            lang = self._command_lang
            if lang == "auto":
                lang = TEXT_MODES[self._mode_index].language
        cmd_key = LANG_TO_CMD.get(lang, "command-russian")
        return next((m for m in MODES if m.key == cmd_key), MODES[-1])

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

    def model_name(self) -> str | None:
        with self._lock:
            return self._model_name

    def save_model_name(self, name: str | None) -> None:
        try:
            raw: dict[str, Any] = json.loads(self._config_file.read_text())
        except Exception:
            raw = {}
        if name is None:
            raw.pop("selected_model", None)
        else:
            raw["selected_model"] = name
        self._config_file.write_text(json.dumps(raw, indent=4))
        with self._lock:
            self._model_name = name

    def command_lang(self) -> str:
        with self._lock:
            return self._command_lang

    def commands_enabled(self) -> bool:
        with self._lock:
            return self._commands_enabled

    def save_command_lang(self, lang: str) -> None:
        try:
            raw: dict[str, Any] = json.loads(self._config_file.read_text())
        except Exception:
            raw = {}
        raw.setdefault("commands", {})["language"] = lang
        self._config_file.write_text(json.dumps(raw, indent=4))
        with self._lock:
            self._command_lang = lang

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
