import logging
import threading
from typing import Any

import numpy as np
import sounddevice as sd

from modes import PREFERRED_MICS, SAMPLE_RATE

logger = logging.getLogger(__name__)


class AudioRecorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recording: bool = False
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._device, self._device_label = AudioRecorder.pick_input_device()

    @staticmethod
    def pick_input_device() -> tuple[int | None, str]:
        devices = sd.query_devices()
        for needle in PREFERRED_MICS:
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0 and needle.lower() in d["name"].lower():
                    return i, d["name"]
        default = sd.query_devices(kind="input")
        return None, default["name"]

    def start(self) -> None:
        with self._lock:
            if self._recording:
                return
            self._recording = True
            self._chunks = []
            self._stream = None

            def cb(indata: np.ndarray, *_: Any) -> None:
                try:
                    self._chunks.append(indata.copy())
                except Exception:
                    logger.exception("Audio callback error — chunk dropped")

            try:
                self._stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    device=self._device,
                    callback=cb,
                )
                self._stream.start()
            except Exception as e:
                self._recording = False
                self._stream = None
                raise RuntimeError(f"Mic error: {e}") from e

    def stop(self) -> np.ndarray:
        with self._lock:
            if not self._recording:
                return np.zeros(0, dtype=np.float32)
            self._recording = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                except Exception:
                    logger.exception("Error stopping audio stream")
                try:
                    self._stream.close()
                except Exception:
                    logger.exception("Error closing audio stream")
                self._stream = None
            chunks = self._chunks
            self._chunks = []

        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks).flatten()

    @property
    def device_name(self) -> str:
        return self._device_label

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording
