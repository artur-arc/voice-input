"""ctranslate2 worker — runs in an isolated subprocess so native crashes don't kill the tray."""
import os
import struct
import sys

# Must be set before ctranslate2 is imported.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("CT2_FORCE_CPU_ISA", "GENERIC")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

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


def main() -> None:
    model_name = _rs()
    compute_type = _rs()

    try:
        from faster_whisper import WhisperModel  # type: ignore[import]
        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type=compute_type,
            cpu_threads=1,
            num_workers=1,
        )
        _ws("READY")
    except Exception as exc:
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
