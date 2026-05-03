"""ctranslate2 worker — runs in an isolated subprocess so native crashes don't kill the tray."""
import os
import struct
import sys

# Must be set before ctranslate2 is imported.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("CT2_FORCE_CPU_ISA", "GENERIC")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("CT2_VERBOSE", "1")

import numpy as np  # noqa: E402 — after env vars

_RD = sys.stdin.buffer
_WR = sys.stdout.buffer


def _rs() -> str:
    (n,) = struct.unpack(">H", _RD.read(2))
    return _RD.read(n).decode("utf-8")


def _ws(s: str) -> None:
    b = s.encode("utf-8")
    _WR.write(struct.pack(">H", len(b)) + b)
    _WR.flush()


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def main() -> None:
    model_name = _rs()
    compute_type = _rs()

    _log(f"WORKER: start model={model_name} compute_type={compute_type}")

    try:
        import ctranslate2 as _ct2  # type: ignore[import]
        _log(f"WORKER: ctranslate2 version={_ct2.__version__}")
    except Exception as exc:
        _log(f"WORKER: ctranslate2 import error: {exc}")

    try:
        _log("WORKER: importing faster_whisper")
        from faster_whisper import WhisperModel  # type: ignore[import]
        _log("WORKER: faster_whisper imported OK")
    except Exception as exc:
        _log(f"WORKER: faster_whisper import failed: {exc}")
        _ws(f"ERROR:{exc}")
        sys.exit(1)

    _log("WORKER: calling WhisperModel()")
    try:
        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type=compute_type,
            cpu_threads=1,
            num_workers=1,
        )
        _log("WORKER: WhisperModel() OK")
        _ws("READY")
    except Exception as exc:
        _log(f"WORKER: WhisperModel() exception: {exc}")
        _ws(f"ERROR:{exc}")
        sys.exit(1)

    while True:
        header = _RD.read(4)
        if len(header) < 4:
            break
        (n_samples,) = struct.unpack(">I", header)
        if n_samples == 0:
            break
        audio = np.frombuffer(_RD.read(n_samples * 4), dtype=np.float32)
        language = _rs()
        task = _rs()
        prompt = _rs()
        kwargs: dict = {"language": language, "initial_prompt": prompt}
        if task == "translate":
            kwargs["task"] = "translate"
        try:
            segments, _ = model.transcribe(audio, **kwargs)
            _ws(" ".join(s.text for s in segments).strip())
        except Exception:
            _ws("")
            break


if __name__ == "__main__":
    main()
