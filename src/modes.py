from dataclasses import dataclass
from typing import Final, Literal

SAMPLE_RATE: Final[int] = 16000
MODEL_REPO: Final[str] = "mlx-community/whisper-large-v3-mlx"
MIN_RECORD_SEC: Final[float] = 0.3
PREFERRED_MICS: Final[tuple[str, ...]] = ("EMEET", "USB")


@dataclass(frozen=True)
class Mode:
    key: str
    label: str
    task: Literal["translate", "transcribe"]
    language: str


MODES: Final[tuple[Mode, ...]] = (
    Mode(key="russian-english", label="ru→en",  task="translate",  language="ru"),
    Mode(key="russian-russian", label="ru→ru",  task="transcribe", language="ru"),
    Mode(key="english-english", label="en→en",  task="transcribe", language="en"),
    Mode(key="hebrew-english",  label="he→en",  task="translate",  language="he"),
    Mode(key="hebrew-hebrew",   label="he→he",  task="transcribe", language="he"),
    Mode(key="command-russian", label="cmd·ru", task="transcribe", language="ru"),
    Mode(key="command-english", label="cmd·en", task="transcribe", language="en"),
    Mode(key="command-hebrew",  label="cmd·he", task="transcribe", language="he"),
)
