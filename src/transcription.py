"""Speech transcription — mlx-whisper (macOS/Apple Silicon) or faster-whisper (Windows/CPU)."""
from __future__ import annotations

import contextlib
import io
import logging
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


_INT8_TIMEOUT = 300   # seconds per compute_type probe in worker subprocess
_FLOAT32_TIMEOUT = 300

# Cache file: stores the compute_type that worked last time so future starts skip detection
_COMPUTE_TYPE_CACHE = Path(__file__).parent.parent / ".ct2_compute_type"
_WORKER_SCRIPT = Path(__file__).parent / "transcription_worker.py"


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
    """faster-whisper backend — runs ctranslate2 in an isolated subprocess.

    ctranslate2 can crash with STATUS_ACCESS_VIOLATION (0xC0000005) on some CPUs,
    killing the whole Python process. Running it in a subprocess confines any native
    crash to the child, keeping the tray process alive.
    """

    def __init__(self, model_repo: str = MODEL_REPO) -> None:
        self._model_name = _detect_win_model()
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
            cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
            model_dir = cache_dir / f"models--Systran--faster-whisper-{self._model_name}"
            logger.info("Checking model cache: %s", model_dir)

            if not model_dir.exists():
                self._load_error = (
                    f"Model not found at {model_dir}. Re-run setup.py to download it."
                )
                logger.error(self._load_error)
                return

            # Validate model.bin — ctranslate2 crashes with 0xC0000005 on corrupted files.
            _EXPECTED_MIN_MB = {"small": 200, "medium": 400, "large-v3": 1400}
            model_bins = sorted(model_dir.glob("**/model.bin"))
            if not model_bins:
                self._load_error = (
                    f"model.bin not found inside {model_dir}. "
                    "Files may be incomplete — delete the directory and re-run setup.py."
                )
                logger.error(self._load_error)
                return
            model_bin_mb = model_bins[0].stat().st_size / 1_048_576
            min_mb = _EXPECTED_MIN_MB.get(self._model_name, 100)
            logger.info("model.bin: %.1f MB (expected >= %d MB)", model_bin_mb, min_mb)
            if model_bin_mb < min_mb:
                self._load_error = (
                    f"model.bin is {model_bin_mb:.1f} MB — expected >= {min_mb} MB. "
                    f"Files are corrupted or incomplete. "
                    f"Delete {model_dir} and re-run setup.py to re-download."
                )
                logger.error(self._load_error)
                return

            saved_ct = _read_cached_compute_type()
            if saved_ct:
                compute_types = [saved_ct]
                logger.info("Using saved compute_type=%s (from previous run)", saved_ct)
            else:
                compute_types = ["int8", "float32"]
                logger.info("First run — will probe compute_types in subprocess")

            timeouts = {"int8": _INT8_TIMEOUT, "float32": _FLOAT32_TIMEOUT}
            for compute_type in compute_types:
                timeout = timeouts.get(compute_type, _FLOAT32_TIMEOUT)
                logger.info("Probing compute_type=%s in subprocess (timeout=%ds)...",
                            compute_type, timeout)
                proc = self._launch_worker(compute_type, timeout)
                if proc is not None:
                    self._proc = proc
                    logger.info("Worker ready: model=%s compute_type=%s",
                                self._model_name, compute_type)
                    if not saved_ct:
                        _save_cached_compute_type(compute_type)
                        logger.info("Saved compute_type=%s for next run", compute_type)
                    break
                if saved_ct:
                    _COMPUTE_TYPE_CACHE.unlink(missing_ok=True)
                    logger.warning("Cleared cached compute_type — will re-probe next run")
                    saved_ct = None
                    compute_types = ["int8", "float32"]

            if self._proc is None and not self._load_error:
                self._load_error = (
                    "Model failed to load with int8 and float32. "
                    "Likely cause: stale model cache (ctranslate2 format mismatch). "
                    "Fix: delete %USERPROFILE%\\.cache\\huggingface\\hub\\models--Systran--faster-whisper-* "
                    "then re-run setup.py"
                )
                logger.error(self._load_error)

        except Exception as exc:
            self._load_error = str(exc)
            logger.exception("warm_up failed unexpectedly: %s", exc)
        finally:
            self._ready.set()

    def _launch_worker(
        self, compute_type: str, timeout: int
    ) -> "subprocess.Popen[bytes] | None":
        """Start a worker subprocess and wait for it to signal READY.

        If the worker crashes (native segfault, OOM, etc.) it exits with a non-zero
        code; we capture its stderr and log it for diagnosis, then return None.
        """
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
            self._ws(proc, self._model_name)
            self._ws(proc, compute_type)
            response = self._rs(proc, timeout=timeout)
        except Exception as exc:
            logger.error("Worker communication error (ct=%s): %s", compute_type, exc)
            self._terminate(proc)
            return None

        if response == "READY":
            return proc

        # Worker reported an error or crashed — log its stderr for diagnosis
        stderr_out = ""
        try:
            proc.wait(timeout=5)
            raw = proc.stderr.read(65536) if proc.stderr else b""
            stderr_out = raw.decode("utf-8", errors="replace").strip()
        except Exception:
            pass

        if response.startswith("ERROR:"):
            logger.error("Worker init error (ct=%s): %s", compute_type, response[6:])
        else:
            logger.error("Worker init unexpected response (ct=%s): %r", compute_type, response)
        if stderr_out:
            logger.error("Worker stderr (ct=%s):\n%s", compute_type, stderr_out)
        if proc.returncode is not None and proc.returncode != 0:
            rc = proc.returncode & 0xFFFFFFFF
            logger.error("Worker exit code: %d (0x%08X)", proc.returncode, rc)
            if rc == 0xC0000005:
                logger.error(
                    "0xC0000005 = STATUS_ACCESS_VIOLATION — ctranslate2 native crash. "
                    "This often means the cached model is in an old format (ctranslate2 v3) "
                    "incompatible with the installed ctranslate2 v4+. "
                    "Fix: delete the model directory and re-run setup.py to re-download:\n"
                    "  del /s /q %%USERPROFILE%%\\.cache\\huggingface\\hub\\models--Systran--faster-whisper-*"
                )

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
