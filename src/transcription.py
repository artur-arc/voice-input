import logging

import mlx_whisper
import numpy as np

from modes import MIN_RECORD_SEC, MODEL_REPO, SAMPLE_RATE, Mode

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, model_repo: str = MODEL_REPO) -> None:
        self._model_repo = model_repo

    @property
    def model_repo(self) -> str:
        return self._model_repo

    def warm_up(self) -> None:
        try:
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
        """Return transcribed text, or None if audio is too short or result is empty."""
        if len(audio) < SAMPLE_RATE * MIN_RECORD_SEC:
            return None
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self._model_repo,
            task=mode.task,
            language=mode.language,
            # Whisper initial_prompt primes the model for the target language.
            # The Russian string is intentional — improves Russian transcription accuracy.
            initial_prompt=Transcriber._initial_prompt(mode.language),
            verbose=False,
        )
        return result["text"].strip() or None

    @staticmethod
    def _initial_prompt(language: str) -> str:
        if language == "ru":
            return "Привет, давайте обсудим задачу."
        return "Let's discuss the task."
