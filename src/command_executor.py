"""Voice command executor: simple pattern matching + Ollama fallback."""
from __future__ import annotations

import json
import logging
import re
import subprocess
from urllib.parse import quote_plus
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"

# Broad verb-stem match: covers открой/открыть/откроем/открываем/etc.
_V_OPEN  = r"(откр[оыеёиуа]|запуст|включ|вруб|покаж|launch|open|start)"
_V_CLOSE = r"(закр[оыеёиу]|выйд|quit|close)"
_V_MUTE  = r"(выключ|отключ|замьютир|убер|притих|mute)"
_V_UNMUTE = r"(включ|добавь|размьютир|верн|unmute)"
_V_FIND  = r"(найд[иёе]|поищ|поиск|search|найт)"
_V_SHOT  = r"(сделай|сними|снимок|скриншот|screenshot)"

# (regex, action) — checked before Ollama
_SIMPLE: list[tuple[str, str]] = [
    (_V_OPEN  + r".*(браузер|browser)",               "open_browser"),
    (_V_OPEN  + r".*(safari|сафари)",                 "open_safari"),
    (_V_OPEN  + r".*(chrome|хром)",                   "open_chrome"),
    (_V_OPEN  + r".*(firefox|фаерфокс)",              "open_firefox"),
    (_V_OPEN  + r".*(music|itunes|итюнс|музык)",      "open_music"),
    (_V_OPEN  + r".*(terminal|терминал)",             "open_terminal"),
    (_V_OPEN  + r".*(finder|файл|проводник)",         "open_finder"),
    (_V_OPEN  + r".*(notes|заметк)",                  "open_notes"),
    (_V_OPEN  + r".*(settings|preferences|настройк)", "open_settings"),
    (_V_OPEN  + r".*(vscode|visual studio|vs code)",  "open_vscode"),
    (_V_OPEN  + r".*(slack|слак)",                    "open_slack"),
    (_V_OPEN  + r".*(telegram|телеграм)",             "open_telegram"),
    (_V_OPEN  + r".*(zoom)",                          "open_zoom"),
    (_V_MUTE  + r".*(звук|аудио|volume|мьют|sound)", "mute"),
    (r"(мьют|mute)\b",                                "mute"),
    (_V_UNMUTE + r".*(звук|аудио|volume|sound)",      "unmute"),
    (_V_SHOT  + r".*(экран|screen|png)?",             "screenshot"),
    (r"\bscreenshot\b",                               "screenshot"),
]

# macOS app name lookup (handles Russian names from Ollama)
_APP_MAP: dict[str, str] = {
    "safari":         "Safari",
    "сафари":         "Safari",
    "браузер":        "__default_browser__",
    "browser":        "__default_browser__",
    "chrome":         "Google Chrome",
    "google chrome":  "Google Chrome",
    "хром":           "Google Chrome",
    "firefox":        "Firefox",
    "фаерфокс":       "Firefox",
    "music":          "Music",
    "itunes":         "Music",
    "итюнс":          "Music",
    "музыка":         "Music",
    "terminal":       "Terminal",
    "терминал":       "Terminal",
    "finder":         "Finder",
    "файлы":          "Finder",
    "notes":          "Notes",
    "заметки":        "Notes",
    "settings":       "System Settings",
    "system settings":"System Settings",
    "настройки":      "System Settings",
    "vscode":         "Visual Studio Code",
    "vs code":        "Visual Studio Code",
    "visual studio":  "Visual Studio Code",
    "slack":          "Slack",
    "слак":           "Slack",
    "telegram":       "Telegram",
    "телеграм":       "Telegram",
    "zoom":           "zoom.us",
}

_SYSTEM_PROMPT = """\
You are a macOS voice command assistant. The user speaks in Russian.
Return ONLY a JSON object — no explanation, no markdown.

Supported actions and examples:

{"action": "open_safari"}                            — open browser / открой браузер / сафари
{"action": "open_chrome"}                            — открой хром / chrome
{"action": "open_music"}                             — открой музыку / itunes / итюнс
{"action": "open_terminal"}                          — открой терминал
{"action": "open_finder"}                            — открой finder / файлы
{"action": "open_notes"}                             — открой заметки
{"action": "open_settings"}                          — открой настройки
{"action": "open_slack"}                             — открой slack / слак
{"action": "open_telegram"}                          — открой телеграм
{"action": "open_zoom"}                              — открой zoom
{"action": "mute"}                                   — выключи звук / замьютируй
{"action": "unmute"}                                 — включи звук / размьютируй
{"action": "screenshot"}                             — скриншот / сделай снимок экрана
{"action": "google_search", "query": "iPhone 17"}   — найди iPhone 17 / поищи в гугле
{"action": "youtube_search", "query": "котики"}     — найди на youtube / ютубе
{"action": "open_url", "url": "https://..."}         — открой сайт / ссылку
{"action": "unknown"}                                — anything else

Choose the best match. Return ONLY the JSON.
"""


def _run(cmd: list[str]) -> None:
    subprocess.Popen(cmd)


def _osascript(script: str) -> None:
    subprocess.run(["osascript", "-e", script], check=False)


def _resolve_app_name(name: str) -> str:
    """Convert Russian or shorthand app name to macOS app name."""
    return _APP_MAP.get(name.lower().strip(), name)


def _execute(action: dict) -> None:
    name = action.get("action", "unknown")

    _STATIC_CMDS: dict[str, list[str]] = {
        "open_browser":  ["open", "https://www.google.com"],
        "open_safari":   ["open", "-a", "Safari"],
        "open_chrome":   ["open", "-a", "Google Chrome"],
        "open_firefox":  ["open", "-a", "Firefox"],
        "open_music":    ["open", "-a", "Music"],
        "open_terminal": ["open", "-a", "Terminal"],
        "open_finder":   ["open", "-a", "Finder"],
        "open_notes":    ["open", "-a", "Notes"],
        "open_settings": ["open", "-a", "System Settings"],
        "open_vscode":   ["open", "-a", "Visual Studio Code"],
        "open_slack":    ["open", "-a", "Slack"],
        "open_telegram": ["open", "-a", "Telegram"],
        "open_zoom":     ["open", "-a", "zoom.us"],
    }

    if name in _STATIC_CMDS:
        _run(_STATIC_CMDS[name])
        logger.info("Executed: %s", name)

    elif name == "open_app":
        app = _resolve_app_name(action.get("app", ""))
        if app == "__default_browser__":
            _run(["open", "https://www.google.com"])
            logger.info("Opened default browser")
        else:
            _run(["open", "-a", app])
            logger.info("Opened app: %s", app)

    elif name == "mute":
        _osascript("set volume output muted true")
        logger.info("Muted")

    elif name == "unmute":
        _osascript("set volume output muted false")
        logger.info("Unmuted")

    elif name == "screenshot":
        from pathlib import Path
        dest = str(Path.home() / "Desktop" / "screenshot.png")
        _run(["screencapture", "-iW", dest])
        logger.info("Screenshot → %s", dest)

    elif name == "google_search":
        query = action.get("query", "")
        _run(["open", f"https://www.google.com/search?q={quote_plus(query)}"])
        logger.info("Google search: %s", query)

    elif name == "youtube_search":
        query = action.get("query", "")
        _run(["open", f"https://www.youtube.com/search?query={quote_plus(query)}"])
        logger.info("YouTube search: %s", query)

    elif name == "open_url":
        _run(["open", action.get("url", "")])
        logger.info("Opened URL: %s", action.get("url"))

    elif name == "unknown":
        logger.warning("Command not understood")

    else:
        # Last resort: Ollama returned open_app with a Russian name
        logger.warning("Unhandled action '%s', trying as app name", name)


def _try_simple(text: str) -> bool:
    lower = text.lower()
    for pattern, action in _SIMPLE:
        if re.search(pattern, lower):
            _execute({"action": action})
            return True
    return False


def _ask_ollama(text: str) -> dict:
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "system": _SYSTEM_PROMPT,
        "prompt": f'Command: "{text}"\nJSON:',
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0, "num_predict": 80},
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            parsed = json.loads(result.get("response", "{}"))
            # If Ollama returned open_app with a Russian name, normalise it
            if parsed.get("action") == "open_app":
                resolved = _resolve_app_name(parsed.get("app", ""))
                if resolved != parsed.get("app"):
                    parsed["app"] = resolved
            return parsed
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        logger.error("Ollama error: %s", exc)
        return {"action": "unknown"}


def handle(text: str) -> bool:
    """Execute a voice command. Returns True if recognized, False if unknown."""
    if _try_simple(text):
        return True

    logger.info("Sending to Ollama: %s", text)
    action = _ask_ollama(text)
    logger.info("Ollama result: %s", action)

    if action.get("action") == "unknown":
        logger.warning("Not understood: %s", text)
        return False

    _execute(action)
    return True
