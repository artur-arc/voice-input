"""Speech transcription — mlx-whisper (macOS/Apple Silicon) or faster-whisper (Windows/CPU)."""
from __future__ import annotations

import contextlib
import io
import logging
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import numpy as np

from modes import MIN_RECORD_SEC, MODEL_REPO, SAMPLE_RATE, Mode

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


def _detect_win_model() -> str:
    """Choose faster-whisper model based on total physical RAM.

    setup.py guarantees the cache always contains the RAM-appropriate model,
    so we select by RAM here without inspecting the cache.
    """
    import ctypes

    class _MemStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength",                ctypes.c_ulong),
            ("dwMemoryLoad",            ctypes.c_ulong),
            ("ullTotalPhys",            ctypes.c_ulonglong),
            ("ullAvailPhys",            ctypes.c_ulonglong),
            ("ullTotalPageFile",        ctypes.c_ulonglong),
            ("ullAvailPageFile",        ctypes.c_ulonglong),
            ("ullTotalVirtual",         ctypes.c_ulonglong),
            ("ullAvailVirtual",         ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    try:
        mem = _MemStatus()
        mem.dwLength = ctypes.sizeof(mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))  # type: ignore[attr-defined]
        total_gb = mem.ullTotalPhys / (1024 ** 3)
    except Exception:
        total_gb = 0.0

    if total_gb >= 16:
        return "large-v3"
    elif total_gb >= 8:
        return "medium"
    else:
        return "small"


class Transcriber(ABC):
    """Platform-agnostic transcription interface.

    Instantiating ``Transcriber(model_repo)`` returns the correct backend:
    - macOS: ``_MacTranscriber`` using mlx-whisper (Apple Silicon, fast)
    - Windows: ``_WindowsTranscriber`` using faster-whisper (CPU, int8)
    """

    def __new__(cls, model_repo: str = MODEL_REPO) -> "Transcriber":
        if cls is Transcriber:
            impl = _WindowsTranscriber if sys.platform == "win32" else _MacTranscriber
            return super().__new__(impl)
        return super().__new__(cls)

    @property
    @abstractmethod
    def model_repo(self) -> str: ...

    def is_ready(self) -> bool:
        """Return True when the model is loaded and ready to transcribe."""
        return True

    @abstractmethod
    def warm_up(self) -> None: ...

    @abstractmethod
    def transcribe(self, audio: np.ndarray, mode: Mode) -> str | None: ...

    @staticmethod
    def _initial_prompt(language: str) -> str:
        if language == "ru":
            return "Привет, давайте обсудим задачу."
        return "Let's discuss the task."


class _MacTranscriber(Transcriber):
    """mlx-whisper backend — Apple Silicon only."""

    def __init__(self, model_repo: str = MODEL_REPO) -> None:
        self._model_repo = model_repo

    @property
    def model_repo(self) -> str:
        return self._model_repo

    def warm_up(self) -> None:
        import mlx_whisper  # lazy — macOS only package
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                mlx_whisper.transcribe(
                    np.zeros(SAMPLE_RATE, dtype=np.float32),
                    path_or_hf_repo=self._model_repo,
                    language="en",
                    verbose=False,
                )
            logger.info("Model warm-up complete: %s", self._model_repo)
        except Exception:
            logger.exception("Model warm-up failed for %s", self._model_repo)
            raise

    def transcribe(self, audio: np.ndarray, mode: Mode) -> str | None:
        import mlx_whisper  # lazy — macOS only package
        if len(audio) < SAMPLE_RATE * MIN_RECORD_SEC:
            return None
        with contextlib.redirect_stderr(io.StringIO()):
            result = mlx_whisper.transcribe(
                audio,
                path_or_hf_repo=self._model_repo,
                task=mode.task,
                language=mode.language,
                # The Russian string primes the model for Russian transcription accuracy.
                initial_prompt=self._initial_prompt(mode.language),
                verbose=False,
            )
        return result["text"].strip() or None


_WARM_UP_TIMEOUT = 300  # seconds — ctranslate2 can hang on certain CPUs


class _WindowsTranscriber(Transcriber):
    """faster-whisper backend — Windows/CPU (int8 quantization)."""

    def __init__(self, model_repo: str = MODEL_REPO) -> None:
        import threading
        self._model_name = _detect_win_model()
        self._model: WhisperModel | None = None
        self._ready = threading.Event()
        self._load_error: str | None = None
        logger.info("Windows model selected: %s", self._model_name)

    @property
    def model_repo(self) -> str:
        return self._model_name

    def is_ready(self) -> bool:
        return self._ready.is_set()

    def warm_up(self) -> None:
        import threading
        from pathlib import Path
        from faster_whisper import WhisperModel  # lazy — Windows only package

        try:
            cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
            model_dir = cache_dir / f"models--Systran--faster-whisper-{self._model_name}"
            logger.info("Checking model cache: %s", model_dir)

            if not model_dir.exists():
                self._load_error = (
                    f"Model not found at {model_dir}. Re-run setup.py to download it."
                )
                logger.error(self._load_error)
                return

            logger.info("Model found in cache — loading (may take up to %ds)...", _WARM_UP_TIMEOUT)

            # Run WhisperModel() in a sub-thread with a timeout.
            # ctranslate2 can hang indefinitely on certain CPUs without raising an exception.
            load_error: list[str] = []
            loaded_model: list[Any] = []

            def _load() -> None:
                try:
                    m = WhisperModel(self._model_name, device="cpu", compute_type="int8")
                    loaded_model.append(m)
                except Exception as exc:
                    load_error.append(str(exc))
                    logger.exception("Model load failed: %s", exc)

            t = threading.Thread(target=_load, daemon=True)
            t.start()
            t.join(timeout=_WARM_UP_TIMEOUT)

            if t.is_alive():
                self._load_error = (
                    f"Model load timed out after {_WARM_UP_TIMEOUT}s. "
                    "ctranslate2 may not support this CPU. Try a different compute_type."
                )
                logger.error(self._load_error)
            elif load_error:
                self._load_error = load_error[0]
            elif loaded_model:
                self._model = loaded_model[0]
                logger.info("Model loaded: %s", self._model_name)
            else:
                self._load_error = "Model load thread exited without result"
                logger.error(self._load_error)

        except Exception as exc:
            self._load_error = str(exc)
            logger.exception("warm_up failed unexpectedly: %s", exc)
        finally:
            self._ready.set()

    def transcribe(self, audio: np.ndarray, mode: Mode) -> str | None:
        if len(audio) < SAMPLE_RATE * MIN_RECORD_SEC:
            return None
        if not self._ready.is_set():
            logger.info("Waiting for model to load...")
            self._ready.wait()  # wait indefinitely — audio must not be lost on slow machines
            logger.info("Model ready — processing audio")
        if self._model is None:
            logger.error("Model unavailable (load error: %s)", self._load_error)
            return None
        kwargs: dict[str, Any] = {
            "language": mode.language,
            "initial_prompt": self._initial_prompt(mode.language),
        }
        if mode.task == "translate":
            kwargs["task"] = "translate"
        segments, _ = self._model.transcribe(audio, **kwargs)
        return " ".join(s.text for s in segments).strip() or None
