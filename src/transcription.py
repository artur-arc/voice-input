"""Speech transcription — mlx-whisper (macOS/Apple Silicon) or faster-whisper (Windows/CPU)."""
from __future__ import annotations

import contextlib
import io
import logging
import os
import queue
import struct
import subprocess
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

    if total_gb >= 14:
        return "large-v3"
    elif total_gb >= 4:
        return "medium"
    else:
        return "tiny"


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


_LOAD_TIMEOUT = 60  # seconds to wait for worker to signal READY
_MODELS_DIR = Path(__file__).parent.parent / "models"
_WORKER_SCRIPT = Path(__file__).parent / "transcription_worker.py"


class _WindowsTranscriber(Transcriber):
    """pywhispercpp (whisper.cpp) backend — no ctranslate2, runs in isolated subprocess."""

    def __init__(self, model_repo: str = MODEL_REPO) -> None:
        self._model_name = _detect_win_model()
        self._model_path = str(_MODELS_DIR / f"ggml-{self._model_name}.bin")
        self._proc: subprocess.Popen[bytes] | None = None
        self._ready = threading.Event()
        self._load_error: str | None = None
        self._io_lock = threading.Lock()
        logger.info("Windows model selected: %s", self._model_name)

    @property
    def model_repo(self) -> str:
        return self._model_name

    def is_ready(self) -> bool:
        return self._ready.is_set()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def warm_up(self) -> None:
        try:
            model_file = Path(self._model_path)
            logger.info("Checking model: %s", model_file)

            if not model_file.exists():
                self._load_error = (
                    f"Model not found at {model_file}. Re-run install.bat to download it."
                )
                logger.error(self._load_error)
                return

            size_mb = model_file.stat().st_size / 1_048_576
            logger.info("Model size: %.1f MB", size_mb)

            proc = self._launch_worker(_LOAD_TIMEOUT)
            if proc is not None:
                self._proc = proc
                logger.info("Worker ready: %s", model_file.name)
            elif not self._load_error:
                self._load_error = "Model failed to load. Re-run install.bat."
                logger.error(self._load_error)

        except Exception as exc:
            self._load_error = str(exc)
            logger.exception("warm_up failed unexpectedly: %s", exc)
        finally:
            self._ready.set()

    def _launch_worker(self, timeout: int) -> "subprocess.Popen[bytes] | None":
        try:
            proc = subprocess.Popen(
                [sys.executable, str(_WORKER_SCRIPT)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as exc:
            logger.error("Failed to start worker process: %s", exc)
            return None

        try:
            self._ws(proc, self._model_path)
            self._ws(proc, "")  # dummy — IPC slot kept for protocol compatibility
            response = self._rs(proc, timeout=timeout)
        except Exception as exc:
            logger.error("Worker communication error: %s", exc)
            self._terminate(proc)
            return None

        if response == "READY":
            return proc

        stderr_out = ""
        try:
            proc.wait(timeout=5)
            raw = proc.stderr.read(65536) if proc.stderr else b""
            stderr_out = raw.decode("utf-8", errors="replace").strip()
        except Exception:
            pass

        if response.startswith("ERROR:"):
            logger.error("Worker init error: %s", response[6:])
        else:
            logger.error("Worker init unexpected response: %r", response)
        if stderr_out:
            logger.error("Worker stderr:\n%s", stderr_out)
        if proc.returncode is not None and proc.returncode != 0:
            logger.error("Worker exit code: %d (0x%08X)",
                         proc.returncode, proc.returncode & 0xFFFFFFFF)

        self._terminate(proc)
        return None

    # ── Transcription ─────────────────────────────────────────────────────────

    def transcribe(self, audio: np.ndarray, mode: Mode) -> str | None:
        if len(audio) < SAMPLE_RATE * MIN_RECORD_SEC:
            return None
        if not self._ready.is_set():
            logger.info("Waiting for worker to load...")
            self._ready.wait()
        if self._proc is None:
            logger.error("Worker unavailable: %s", self._load_error)
            return None
        if self._proc.poll() is not None:
            logger.error("Worker process has exited unexpectedly (rc=%d)", self._proc.returncode)
            return None

        with self._io_lock:
            try:
                assert self._proc.stdin and self._proc.stdout
                self._proc.stdin.write(struct.pack(">I", len(audio)))
                self._proc.stdin.write(audio.astype(np.float32).tobytes())
                self._proc.stdin.flush()
                self._ws(self._proc, mode.language)
                self._ws(self._proc, mode.task)
                self._ws(self._proc, self._initial_prompt(mode.language))
                return self._rs(self._proc, timeout=60) or None
            except Exception as exc:
                logger.error("Transcription pipe error: %s", exc)
                return None

    # ── IPC helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _ws(proc: "subprocess.Popen[bytes]", s: str) -> None:
        b = s.encode("utf-8")
        assert proc.stdin
        proc.stdin.write(struct.pack(">H", len(b)) + b)
        proc.stdin.flush()

    @staticmethod
    def _rs(proc: "subprocess.Popen[bytes]", timeout: int) -> str:
        """Read a length-prefixed UTF-8 string from the worker stdout with a timeout."""
        result_q: queue.Queue[str | Exception] = queue.Queue()

        def _read() -> None:
            try:
                assert proc.stdout
                header = proc.stdout.read(2)
                if len(header) < 2:
                    result_q.put("")
                    return
                (n,) = struct.unpack(">H", header)
                result_q.put(proc.stdout.read(n).decode("utf-8"))
            except Exception as exc:
                result_q.put(exc)

        threading.Thread(target=_read, daemon=True).start()
        try:
            val = result_q.get(timeout=timeout)
            if isinstance(val, Exception):
                raise val
            return val
        except queue.Empty:
            logger.warning("Worker response timed out after %ds", timeout)
            return ""

    @staticmethod
    def _terminate(proc: "subprocess.Popen[bytes]") -> None:
        try:
            proc.terminate()
        except Exception:
            pass
