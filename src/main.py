"""Hold Right Cmd to record speech. Right Option to cycle language mode."""
from pathlib import Path
from typing import Final

from app import VoiceInputApp
from audio import AudioRecorder
from config import ConfigManager
from feedback import UserFeedback
from modes import MODEL_REPO
from transcription import Transcriber

CONFIG_FILE: Final[Path] = Path(__file__).parent.parent / "voice-input-config.json"


def main() -> None:
    config = ConfigManager(CONFIG_FILE)
    recorder = AudioRecorder()
    transcriber = Transcriber(MODEL_REPO)
    feedback = UserFeedback()
    VoiceInputApp(config, recorder, transcriber, feedback).start()


if __name__ == "__main__":
    main()
