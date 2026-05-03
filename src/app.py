import logging
import threading
import time
from typing import Final

import numpy as np
from pynput import keyboard
from pynput.keyboard import Key, KeyCode

from audio import AudioRecorder
from config import ConfigManager
from feedback import UserFeedback
from modes import MIN_RECORD_SEC, MODES, SAMPLE_RATE
from paste_util import accessibility_binary, has_accessibility, paste_text
from transcription import Transcriber

RECORD_KEY: Final[Key] = Key.cmd_r
MODE_KEY: Final[Key] = Key.alt_r

logger = logging.getLogger(__name__)

_LISTENER_MAX_RESTARTS: Final[int] = 5
_LISTENER_RESTART_DELAY: Final[float] = 1.0


class VoiceInputApp:
    def __init__(
        self,
        config: ConfigManager,
        recorder: AudioRecorder,
        transcriber: Transcriber,
        feedback: UserFeedback,
    ) -> None:
        self._config = config
        self._recorder = recorder
        self._transcriber = transcriber
        self._feedback = feedback

    def start(self) -> None:
        self._config.load()
        logger.info("Mic: %s", self._recorder.device_name)
        logger.info("Loading %s...", self._transcriber.model_repo)
        self._transcriber.warm_up()

        m = self._config.current_mode()
        ax_ok = has_accessibility()
        logger.info(
            "Ready. Mode: %s | accessibility: %s",
            m.label,
            "yes" if ax_ok else "no (paste disabled)",
        )
        if not ax_ok:
            logger.warning(
                "Add to Accessibility: System Settings > Privacy & Security > Accessibility"
            )
            logger.warning("Binary: %s", accessibility_binary())
        self._feedback.notify(
            "Voice Input",
            f"Ready · {m.label}" + ("" if ax_ok else " · no paste"),
        )
        self._config.watch(self._on_config_change)
        self._run_listener()

    def _run_listener(self) -> None:
        attempts = 0
        while attempts < _LISTENER_MAX_RESTARTS:
            try:
                with keyboard.Listener(
                    on_press=self._on_press,
                    on_release=self._on_release,
                ) as listener:
                    listener.join()
                return  # clean exit
            except Exception:
                attempts += 1
                logger.exception(
                    "Keyboard listener crashed (attempt %d/%d)",
                    attempts,
                    _LISTENER_MAX_RESTARTS,
                )
                if attempts < _LISTENER_MAX_RESTARTS:
                    time.sleep(_LISTENER_RESTART_DELAY)
        logger.error(
            "Keyboard listener failed %d times — giving up", _LISTENER_MAX_RESTARTS
        )

    def _on_press(self, key: Key | KeyCode | None) -> None:
        if key == RECORD_KEY:
            self._start_recording()
        elif key == MODE_KEY:
            self._cycle_mode()

    def _on_release(self, key: Key | KeyCode | None) -> None:
        if key == RECORD_KEY:
            self._stop_and_transcribe()

    def _cycle_mode(self) -> None:
        current = self._config.current_mode()
        new_index = (MODES.index(current) + 1) % len(MODES)
        self._config.save(new_index)
        m = self._config.current_mode()
        logger.info("Mode → %s", m.label)
        self._feedback.notify("Voice Input", f"Mode: {m.label}")
        self._feedback.play("Tink")

    def _start_recording(self) -> None:
        try:
            self._recorder.start()
        except Exception:
            logger.exception("Failed to start recording")
            self._feedback.play("Funk")
            return
        self._feedback.play("Tink")

    def _stop_and_transcribe(self) -> None:
        audio = self._recorder.stop()
        if len(audio) < SAMPLE_RATE * MIN_RECORD_SEC:
            return
        threading.Thread(
            target=self._transcribe_and_paste,
            args=(audio,),
            daemon=True,
        ).start()

    def _transcribe_and_paste(self, audio: np.ndarray) -> None:
        m = self._config.current_mode()
        try:
            t0 = time.time()
            text = self._transcriber.transcribe(audio, m)

            if not text:
                logger.warning("[%.1fs] No speech detected", time.time() - t0)
                self._feedback.play("Funk")
                return

            elapsed = time.time() - t0
            logger.info("[%.1fs] [%s] %s", elapsed, m.label, text)

            pasted = paste_text(text)
            if not pasted:
                logger.warning(
                    "Text placed in clipboard — grant Accessibility to enable auto-paste"
                )
            self._feedback.play("Pop")
        except Exception:
            logger.exception("Transcription/paste error")
            self._feedback.play("Funk")

    def _on_config_change(self, _index: int) -> None:
        logger.info("Config reloaded → mode: %s", self._config.current_mode().label)
