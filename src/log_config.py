import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


class _FlushingRotatingFileHandler(RotatingFileHandler):
    """Flush to disk after every record — survives native crashes (e.g. ctranslate2 segfault)."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


def setup_logging(log_file: Path | None = None) -> None:
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Silence noisy third-party loggers that flood the log with HTTP 200 lines
    for noisy in ("httpx", "httpcore", "huggingface_hub", "filelock", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(fmt)
    root.addHandler(stdout_handler)

    if log_file is not None:
        file_handler = _FlushingRotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
