"""Hold Right Cmd to record speech. Right Option to cycle language mode."""
import os

# Must be set before any library imports tqdm or huggingface_hub.
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import logging
import sys
from pathlib import Path
from typing import Final

from app import VoiceInputApp
from audio import AudioRecorder
from config import ConfigManager
from feedback import UserFeedback
from log_config import setup_logging
from modes import MODEL_REPO
from transcription import Transcriber

CONFIG_FILE: Final[Path] = Path(__file__).parent.parent / "voice-input-config.json"
LOG_FILE: Final[Path] = Path(__file__).parent.parent / "voice_input.log"

logger = logging.getLogger(__name__)


def main() -> None:
    if sys.platform == "win32":
        from tray_windows import main as _win_main
        _win_main()
        return
    config = ConfigManager(CONFIG_FILE)
    recorder = AudioRecorder()
    transcriber = Transcriber(MODEL_REPO)
    feedback = UserFeedback()
    VoiceInputApp(config, recorder, transcriber, feedback).start()


if __name__ == "__main__":
    # When stdout is redirected (launchd), it already captures to voice_input.log.
    # Add RotatingFileHandler only for interactive runs to keep a persistent log.
    setup_logging(LOG_FILE if sys.stdout.isatty() else None)
    try:
        main()
    except Exception:
        logger.exception("Unhandled exception in main — exiting")
        sys.exit(1)
