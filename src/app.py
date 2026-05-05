import logging
import sys
import threading
import time
from typing import Final

import numpy as np
from pynput import keyboard
from pynput.keyboard import Key, KeyCode

from audio import AudioRecorder
from config import ConfigManager
from feedback import UserFeedback
from modes import MIN_RECORD_SEC, SAMPLE_RATE
from paste_util import accessibility_binary, has_accessibility, paste_text
from transcription import Transcriber

if sys.platform == "win32":
    COMMAND_KEY: Final[Key] = Key.ctrl_r  # hold → voice command
    TEXT_KEY: Final[Key]    = Key.alt_r   # hold → transcribe + paste
else:
    COMMAND_KEY: Final[Key] = Key.cmd_r   # hold → voice command
    TEXT_KEY: Final[Key]    = Key.alt_r   # hold → transcribe + paste

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
        self._active_key: Key | None = None

    def start(self) -> None:
        self._config.load()
        self._feedback.sounds_enabled = self._config.sounds_enabled()
        self._feedback.notifications_enabled = self._config.notifications_enabled()
        self._log_device_info()
        logger.info("Loading %s...", self._transcriber.model_repo)
        self._transcriber.warm_up()

        ax_ok = has_accessibility()
        cmd_ok = self._config.commands_enabled()
        if sys.platform == "win32":
            hint = "RCtrl=cmd · RAlt=text" if cmd_ok else "RAlt=text"
            logger.info("Ready. %s", hint)
            self._feedback.notify("Voice Input", f"Ready · {hint}")
        else:
            cmd_part = "cmd_r=command · " if cmd_ok else ""
            logger.info(
                "Ready. %salt_r=text | accessibility: %s",
                cmd_part,
                "yes" if ax_ok else "no (paste disabled)",
            )
            if not ax_ok:
                logger.warning(
                    "Add to Accessibility: System Settings > Privacy & Security > Accessibility"
                )
                logger.warning("Binary: %s", accessibility_binary())
            ui_cmd = "Cmd=cmd · " if cmd_ok else ""
            self._feedback.notify(
                "Voice Input",
                f"Ready · {ui_cmd}Opt=text" + ("" if ax_ok else " · no paste"),
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
                attempts += 1
                logger.warning(
                    "Keyboard listener stopped unexpectedly (attempt %d/%d) — restarting",
                    attempts,
                    _LISTENER_MAX_RESTARTS,
                )
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
        if key == COMMAND_KEY and not self._config.commands_enabled():
            return
        if key in (COMMAND_KEY, TEXT_KEY) and self._active_key is None:
            self._active_key = key
            self._start_recording()

    def _on_release(self, key: Key | KeyCode | None) -> None:
        if key == self._active_key:
            self._active_key = None
            self._stop_and_transcribe(key)

    def _log_device_info(self) -> None:
        configured = self._config.input_device()
        if configured:
            logger.info("Mic (configured): %s", self._recorder.device_name)
        else:
            logger.info("Mic (auto): %s", self._recorder.device_name)
            available = AudioRecorder.list_input_devices()
            if len(available) > 1:
                for dev in available:
                    logger.info("  available: [%d] %s", dev["index"], dev["name"])
                logger.info('To pin a device set "input_device" in voice-input-config.json')

    def _start_recording(self) -> None:
        try:
            self._recorder.start(self._config.input_device())
        except Exception:
            logger.exception("Failed to start recording")
            self._feedback.play("Funk")
            return
        self._feedback.play("Tink")

    def _stop_and_transcribe(self, key: Key) -> None:
        audio = self._recorder.stop()
        if len(audio) < SAMPLE_RATE * MIN_RECORD_SEC:
            return
        threading.Thread(
            target=self._transcribe_and_handle,
            args=(audio, key),
            daemon=True,
        ).start()

    def _transcribe_and_handle(self, audio: np.ndarray, key: Key) -> None:
        is_command = key == COMMAND_KEY
        m = self._config.command_mode() if is_command else self._config.current_mode()
        try:
            t0 = time.time()
            text = self._transcriber.transcribe(audio, m)

            if not text:
                logger.warning("[%.1fs] No speech detected", time.time() - t0)
                self._feedback.play("Funk")
                return

            elapsed = time.time() - t0
            logger.info("[%.1fs] [%s] %s", elapsed, m.label, text)

            if is_command:
                from command_executor import handle as execute_command
                recognized = execute_command(text, lang=m.language)
                self._feedback.play("Pop" if recognized else "Funk")
            else:
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
        logger.info("Config reloaded")
        self._feedback.sounds_enabled = self._config.sounds_enabled()
        self._feedback.notifications_enabled = self._config.notifications_enabled()
