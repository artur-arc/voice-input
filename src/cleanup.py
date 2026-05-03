import re
import ollama

CLEANUP_MIN_WORDS = 5

_RU_FILLERS = re.compile(
    r'\b(э+м?|м{2,}|ну\s+вот|как\s+бы|типа|короче|значит|вот)\b',
    re.IGNORECASE,
)
_EN_FILLERS = re.compile(
    r'\b(uh+m?|um+|you\s+know|basically|like)\b',
    re.IGNORECASE,
)

_PROMPTS = {
    "ru": (
        "Исправь голосовую транскрипцию: замени ошибки распознавания, исправь грамматику, добавь пунктуацию, убери слова-паразиты.\n"
        "Правила вывода: один абзац, без пустых строк, без пояснений, без комментариев — только исправленный текст.\n\n"
    ),
    "en": (
        "Fix this voice transcript: correct ASR errors, fix grammar, add punctuation, remove fillers.\n"
        "Output rules: single paragraph, no blank lines, no explanations — corrected text only.\n\n"
    ),
}


class TranscriptCleaner:
    def __init__(self, model: str):
        self.model = model

    def clean(self, text: str, language: str) -> str:
        pattern = _RU_FILLERS if language == "ru" else _EN_FILLERS
        text = pattern.sub("", text)
        text = re.sub(r"\s{2,}", " ", text).strip()

        if len(text.split()) < CLEANUP_MIN_WORDS:
            return text

        prompt = _PROMPTS.get(language, _PROMPTS["en"])
        try:
            resp = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt + text}],
            )
            result = resp["message"]["content"].strip()
            # collapse any blank lines the model snuck in
            result = re.sub(r"\n{2,}", "\n", result)
            return result
        except Exception as e:
            print(f"Ollama cleanup error: {e}")
            return text
