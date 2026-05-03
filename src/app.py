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
        print(f"Mic: {self._recorder.device_name}")
        print(f"Loading {self._transcriber.model_repo}...")
        self._transcriber.warm_up()

        m = self._config.current_mode()
        ax_ok = has_accessibility()
        print(f"Ready. Mode: {m.label} | accessibility: {'✓' if ax_ok else '✗ (paste disabled)'}")
        if not ax_ok:
            print("  → Add to Accessibility: System Settings > Privacy & Security > Accessibility")
            print(f"  → Binary: {accessibility_binary()}")
        self._feedback.notify("Voice Input", f"Ready · {m.label}" + ("" if ax_ok else " · no paste"))
        self._config.watch(self._on_config_change)

        with keyboard.Listener(on_press=self._on_press, on_release=self._on_release) as listener:
            listener.join()

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
        print(f"Mode → {m.label}")
        self._feedback.notify("Voice Input", f"Mode: {m.label}")
        self._feedback.play("Tink")

    def _start_recording(self) -> None:
        try:
            self._recorder.start()
        except Exception as e:
            print(f"Mic error: {e}")
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
                print(f"[{time.time() - t0:.1f}s] (no speech detected)")
                self._feedback.play("Funk")
                return

            elapsed = time.time() - t0
            print(f"[{elapsed:.1f}s] [{m.label}] {text}")

            pasted = paste_text(text)
            if not pasted:
                print("  (text in clipboard — grant Accessibility to enable auto-paste)")
            self._feedback.play("Pop")
        except Exception as e:
            print(f"Error: {e}")
            self._feedback.play("Funk")

    def _on_config_change(self, _index: int) -> None:
        print(f"Config reloaded → mode: {self._config.current_mode().label}")
