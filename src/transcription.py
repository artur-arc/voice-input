"""Speech transcription — mlx-whisper (macOS/Apple Silicon) or faster-whisper (Windows/CPU)."""
from __future__ import annotations

import contextlib
import io
import logging
import sys
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from modes import MIN_RECORD_SEC, MODEL_REPO, SAMPLE_RATE, Mode

if TYPE_CHECKING:
    from faster_whisper import WhisperModel  # type: ignore[import]

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


_INT8_TIMEOUT = 30    # seconds — AVX2 CPU loads small model in <20s; broken AVX2 hangs indefinitely
_FLOAT32_TIMEOUT = 300  # seconds — fallback for CPUs without AVX2; slower but universal

# Cache file: stores the compute_type that worked last time so future starts skip detection
_COMPUTE_TYPE_CACHE = Path(__file__).parent.parent / ".ct2_compute_type"


def _read_cached_compute_type() -> str | None:
    try:
        ct = _COMPUTE_TYPE_CACHE.read_text(encoding="utf-8").strip()
        return ct if ct in ("int8", "float32") else None
    except Exception:
        return None


def _save_cached_compute_type(ct: str) -> None:
    try:
        _COMPUTE_TYPE_CACHE.write_text(ct, encoding="utf-8")
    except Exception:
        pass


class _WindowsTranscriber(Transcriber):
    """faster-whisper backend — Windows/CPU (int8 quantization)."""

    def __init__(self, model_repo: str = MODEL_REPO) -> None:
        self._model_name = _detect_win_model()
        self._model: WhisperModel | None = None
        self._ready = threading.Event()
        self._load_error: str | None = None
        self._transcribe_lock = threading.Lock()
        logger.info("Windows model selected: %s", self._model_name)

    @property
    def model_repo(self) -> str:
        return self._model_name

    def is_ready(self) -> bool:
        return self._ready.is_set()

    def warm_up(self) -> None:
        import os
        import threading
        # OMP_NUM_THREADS=1 prevents OpenMP thread-pool collisions (Intel MKL vs LLVM OMP on Windows).
        # CT2_FORCE_CPU_ISA is intentionally NOT set — let ctranslate2 auto-detect AVX2/AVX.
        # On CPUs with broken AVX2, int8 will time out and we fall back to float32 automatically.
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        from faster_whisper import WhisperModel  # type: ignore[import]  # lazy — Windows only package

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

            # Use saved compute_type from last successful load — skips slow detection.
            saved_ct = _read_cached_compute_type()
            if saved_ct:
                compute_types = [saved_ct]
                logger.info("Using saved compute_type=%s (from previous run)", saved_ct)
            else:
                compute_types = ["int8", "float32"]
                logger.info("First run — will detect best compute_type")

            timeouts = {"int8": _INT8_TIMEOUT, "float32": _FLOAT32_TIMEOUT}
            for compute_type in compute_types:
                timeout = timeouts.get(compute_type, _FLOAT32_TIMEOUT)
                load_error: list[str] = []
                loaded_model: list[Any] = []

                logger.info("Trying compute_type=%s (timeout=%ds)...", compute_type, timeout)

                def _load(ct: str = compute_type) -> None:
                    try:
                        m = WhisperModel(self._model_name, device="cpu", compute_type=ct)
                        loaded_model.append(m)
                    except Exception as exc:
                        load_error.append(str(exc))
                        logger.exception("Model load failed (compute_type=%s): %s", ct, exc)

                t = threading.Thread(target=_load, daemon=True)
                t.start()
                t.join(timeout=timeout)

                if t.is_alive():
                    logger.warning("compute_type=%s timed out after %ds — trying next", compute_type, timeout)
                    if saved_ct:
                        _COMPUTE_TYPE_CACHE.unlink(missing_ok=True)
                        logger.warning("Cleared saved compute_type — will re-detect on next start")
                    continue

                if load_error:
                    logger.warning("compute_type=%s failed — trying next", compute_type)
                    if saved_ct:
                        _COMPUTE_TYPE_CACHE.unlink(missing_ok=True)
                    continue

                if loaded_model:
                    self._model = loaded_model[0]
                    logger.info("Model loaded: %s (compute_type=%s)", self._model_name, compute_type)
                    if not saved_ct:
                        _save_cached_compute_type(compute_type)
                        logger.info("Saved compute_type=%s — next start will be faster", compute_type)
                    break

            if self._model is None and self._load_error is None:
                self._load_error = (
                    "Model failed to load with both int8 and float32. "
                    "Check tray_windows.log for details."
                )
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
        with self._transcribe_lock:
            result: list[Any] = []
            exc_box: list[str] = []

            def _run() -> None:
                try:
                    result.append(self._model.transcribe(audio, **kwargs))  # type: ignore[union-attr]
                except Exception as e:
                    exc_box.append(str(e))

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            t.join(timeout=60)
            if t.is_alive():
                logger.error("Transcription timed out after 60s — model may be stuck")
                return None
            if exc_box:
                logger.error("Transcription error: %s", exc_box[0])
                return None
            if not result:
                return None
            segments, _ = result[0]
        return " ".join(s.text for s in segments).strip() or None
