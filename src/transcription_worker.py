"""pywhispercpp worker — whisper.cpp backend, no ctranslate2."""
import struct
import sys

import numpy as np

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
    model_path = _rs()
    _rs()  # dummy second arg — kept for IPC protocol compatibility

    _log(f"WORKER: start path={model_path}")

    try:
        from pywhispercpp.model import Model  # type: ignore[import]
        _log("WORKER: pywhispercpp imported OK")
    except Exception as exc:
        _log(f"WORKER: import failed: {exc}")
        _ws(f"ERROR:{exc}")
        sys.exit(1)

    _log("WORKER: loading model...")
    try:
        model = Model(model_path, n_threads=4)
        _log("WORKER: model loaded OK")
        _ws("READY")
    except Exception as exc:
        _log(f"WORKER: load failed: {exc}")
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
        _rs()  # prompt

        try:
            segments = model.transcribe(audio, language=language, translate=(task == "translate"))
            _ws(" ".join(s.text for s in segments).strip())
        except Exception as exc:
            _log(f"WORKER: transcribe error: {exc}")
            _ws("")
            break


if __name__ == "__main__":
    main()
