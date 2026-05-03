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
        self._mode_index: int = 1
        self._watch_thread: threading.Thread | None = None

    def load(self) -> None:
        try:
            vcfg = self._read_raw()
            for i, m in enumerate(MODES):
                if vcfg.get(m.key) is True:
                    with self._lock:
                        self._mode_index = i
                    return
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

    def watch(self, on_change: Callable[[int], None]) -> None:
        if self._watch_thread is not None:
            return
        self._watch_thread = threading.Thread(
            target=self._watch_loop,
            args=(on_change,),
            daemon=True,
        )
        self._watch_thread.start()

    def _read_raw(self) -> dict[str, Any]:
        raw: dict[str, Any] = json.loads(self._config_file.read_text())
        return raw.get("voiceInputConfig", raw)

    def _watch_loop(self, on_change: Callable[[int], None]) -> None:
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
