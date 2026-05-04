"""Voice command executor: simple pattern matching + Ollama fallback."""
from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
import time
from urllib.parse import quote_plus
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"

# Broad verb-stem match: covers открой/открыть/откроем/открываем/etc.
_V_OPEN   = r"(откр[оыеёиуа]|запуст|включ|вруб|покаж|launch|open|start|play)"
_V_CLOSE  = r"(закр[оыеёиу]|выйд|quit|close)"
_V_MUTE   = r"(выключ|отключ|замьютир|убер|притих|mute)"
_V_UNMUTE = r"(включ|добавь|размьютир|верн|unmute)"
_V_SHOT   = r"(сделай|сними|снимок|скриншот|screenshot)"
_V_VOL_UP = r"(громч|увелич.*(громк|звук)|погромч|louder|volume.up)"
_V_VOL_DN = r"(тиш|уменьш.*(громк|звук)|потиш|quieter|volume.down)"
_V_SLEEP  = r"(усып[иь]|sleep)"
_V_LOCK   = r"(заблокир|lock)"
_V_MEDIA  = r"(пауз|стоп|останов|pause|stop)"
_V_NEXT   = r"(следующ|дальше|next)"
_V_PREV   = r"(предыдущ|назад|previous|prev|back)"

# (regex, action) — checked before Ollama
_SIMPLE: list[tuple[str, str]] = [
    # Apps
    (_V_OPEN + r".*(браузер|browser)",                "open_browser"),
    (_V_OPEN + r".*(safari|сафари)",                  "open_safari"),
    (_V_OPEN + r".*(chrome|хром)",                    "open_chrome"),
    (_V_OPEN + r".*(firefox|фаерфокс)",               "open_firefox"),
    (_V_OPEN + r".*(spotify|спотифай|спотифи)",       "open_spotify"),
    (_V_OPEN + r".*(music|itunes|итюнс|музык)",       "open_music"),
    (_V_OPEN + r".*(terminal|терминал)",              "open_terminal"),
    (_V_OPEN + r".*(finder|файл|проводник)",          "open_finder"),
    (_V_OPEN + r".*(notes|заметк)",                   "open_notes"),
    (_V_OPEN + r".*(settings|preferences|настройк)",  "open_settings"),
    (_V_OPEN + r".*(vscode|visual studio|vs code)",   "open_vscode"),
    (_V_OPEN + r".*(slack|слак)",                     "open_slack"),
    (_V_OPEN + r".*(telegram|телеграм)",              "open_telegram"),
    (_V_OPEN + r".*(zoom)",                           "open_zoom"),
    # Folders
    (_V_OPEN + r".*(загрузк|download)",               "open_downloads"),
    (_V_OPEN + r".*(документ|document)",              "open_documents"),
    (_V_OPEN + r".*(рабочий стол|desktop)",           "open_desktop"),
    # Volume
    (_V_MUTE  + r".*(звук|аудио|volume|мьют|sound)",  "mute"),
    (r"(мьют|mute)\b",                                 "mute"),
    (_V_UNMUTE + r".*(звук|аудио|volume|sound)",       "unmute"),
    (_V_VOL_UP,                                        "volume_up"),
    (_V_VOL_DN,                                        "volume_down"),
    # Media playback
    (_V_MEDIA,                                         "media_pause"),
    (_V_NEXT + r".*(трек|песн|track|song)?",           "media_next"),
    (_V_PREV + r".*(трек|песн|track|song)?",           "media_prev"),
    # System
    (_V_SLEEP,                                         "sleep"),
    (_V_LOCK  + r".*(экран|screen|компьютер)?",        "lock_screen"),
    (r"(перезагруз|restart|reboot)",                   "restart"),
    (r"(выключ).*(компьютер|mac|систем|pc)",           "shutdown"),
    (r"(очист|пустой|вылей).*(корзин|trash)",          "empty_trash"),
    (r"(покаж|show).*(рабочий стол|desktop)",          "show_desktop"),
    # Screenshot
    (_V_SHOT + r".*(экран|screen|png)?",               "screenshot"),
    (r"\bscreenshot\b",                                "screenshot"),
]

# macOS app name lookup (for Ollama open_app responses)
_APP_MAP: dict[str, str] = {
    "safari":          "Safari",
    "сафари":          "Safari",
    "браузер":         "__default_browser__",
    "browser":         "__default_browser__",
    "chrome":          "Google Chrome",
    "google chrome":   "Google Chrome",
    "хром":            "Google Chrome",
    "firefox":         "Firefox",
    "фаерфокс":        "Firefox",
    "spotify":         "__spotify__",
    "спотифай":        "__spotify__",
    "спотифи":         "__spotify__",
    "music":           "Music",
    "itunes":          "Music",
    "итюнс":           "Music",
    "музыка":          "Music",
    "terminal":        "Terminal",
    "терминал":        "Terminal",
    "finder":          "Finder",
    "файлы":           "Finder",
    "notes":           "Notes",
    "заметки":         "Notes",
    "settings":        "System Settings",
    "system settings": "System Settings",
    "настройки":       "System Settings",
    "vscode":          "Visual Studio Code",
    "vs code":         "Visual Studio Code",
    "visual studio":   "Visual Studio Code",
    "slack":           "Slack",
    "слак":            "Slack",
    "telegram":        "Telegram",
    "телеграм":        "Telegram",
    "zoom":            "zoom.us",
}

_SYSTEM_PROMPT = """\
You are a macOS voice command assistant. The user speaks in Russian, English, or Hebrew.
Return ONLY a JSON object — no explanation, no markdown.

Supported actions:
{"action": "open_browser"}                           — открой браузер / open browser
{"action": "open_spotify"}                           — включи spotify / спотифай
{"action": "open_safari"}                            — открой safari / сафари
{"action": "open_chrome"}                            — открой chrome / хром
{"action": "open_music"}                             — открой музыку / itunes
{"action": "open_terminal"}                          — открой терминал
{"action": "open_finder"}                            — открой finder / файлы
{"action": "open_notes"}                             — открой заметки
{"action": "open_settings"}                          — открой настройки
{"action": "open_slack"}                             — открой slack
{"action": "open_telegram"}                          — открой телеграм
{"action": "open_zoom"}                              — открой zoom
{"action": "open_downloads"}                         — открой загрузки
{"action": "open_documents"}                         — открой документы
{"action": "mute"}                                   — выключи звук / mute
{"action": "unmute"}                                 — включи звук / unmute
{"action": "volume_up"}                              — громче / louder
{"action": "volume_down"}                            — тише / quieter
{"action": "media_pause"}                            — пауза / стоп / pause
{"action": "media_next"}                             — следующий трек / next track
{"action": "media_prev"}                             — предыдущий трек / previous
{"action": "screenshot"}                             — скриншот / screenshot
{"action": "sleep"}                                  — усыпи компьютер / sleep
{"action": "lock_screen"}                            — заблокируй экран / lock
{"action": "restart"}                                — перезагрузи / restart
{"action": "shutdown"}                               — выключи компьютер / shutdown
{"action": "empty_trash"}                            — очисти корзину / empty trash
{"action": "show_desktop"}                           — покажи рабочий стол
{"action": "google_search", "query": "iPhone 17"}   — найди / поищи / search
{"action": "youtube_search", "query": "котики"}     — найди на youtube / ютубе
{"action": "open_url", "url": "https://..."}         — открой сайт / ссылку
{"action": "open_app", "app": "AppName"}             — открой приложение
{"action": "unknown"}                                — anything else

Return ONLY the JSON.
"""


def _run(cmd: list[str]) -> None:
    subprocess.Popen(cmd)


def _osascript(script: str) -> None:
    subprocess.run(["osascript", "-e", script], check=False)


def _press_space_after(delay: float) -> None:
    """Press Space in the frontmost window after a delay (triggers Spotify play)."""
    def _do():
        time.sleep(delay)
        subprocess.run(
            ["osascript", "-e", "tell application \"System Events\" to key code 49"],
            check=False,
        )
    threading.Thread(target=_do, daemon=True).start()


def _confirm(message: str) -> bool:
    """Show a native macOS dialog. Returns True if user clicks OK."""
    result = subprocess.run(
        ["osascript", "-e",
         f'display dialog "{message}" buttons {{"Отмена", "OK"}} default button "Отмена"'],
        capture_output=True,
    )
    return result.returncode == 0


def _resolve_app_name(name: str) -> str:
    return _APP_MAP.get(name.lower().strip(), name)


def _execute(action: dict) -> None:  # noqa: C901
    name = action.get("action", "unknown")

    # Static app launchers
    _APP_CMDS: dict[str, list[str]] = {
        "open_safari":     ["open", "-a", "Safari"],
        "open_chrome":     ["open", "-a", "Google Chrome"],
        "open_firefox":    ["open", "-a", "Firefox"],
        "open_music":      ["open", "-a", "Music"],
        "open_terminal":   ["open", "-a", "Terminal"],
        "open_finder":     ["open", "-a", "Finder"],
        "open_notes":      ["open", "-a", "Notes"],
        "open_settings":   ["open", "-a", "System Settings"],
        "open_vscode":     ["open", "-a", "Visual Studio Code"],
        "open_slack":      ["open", "-a", "Slack"],
        "open_telegram":   ["open", "-a", "Telegram"],
        "open_zoom":       ["open", "-a", "zoom.us"],
    }

    if name == "open_browser":
        _run(["open", "https://www.google.com"])
        logger.info("Opened default browser")

    elif name == "open_spotify":
        _run(["open", "https://open.spotify.com/"])
        _press_space_after(4.0)
        logger.info("Opened Spotify web player")

    elif name in _APP_CMDS:
        _run(_APP_CMDS[name])
        logger.info("Executed: %s", name)

    elif name == "open_downloads":
        from pathlib import Path
        _run(["open", str(Path.home() / "Downloads")])
        logger.info("Opened Downloads")

    elif name == "open_documents":
        from pathlib import Path
        _run(["open", str(Path.home() / "Documents")])
        logger.info("Opened Documents")

    elif name == "open_desktop":
        from pathlib import Path
        _run(["open", str(Path.home() / "Desktop")])
        logger.info("Opened Desktop")

    elif name == "open_app":
        app = _resolve_app_name(action.get("app", ""))
        if app == "__default_browser__":
            _run(["open", "https://www.google.com"])
        elif app == "__spotify__":
            _run(["open", "https://open.spotify.com/"])
        else:
            _run(["open", "-a", app])
        logger.info("Opened app: %s", app)

    elif name == "mute":
        _osascript("set volume output muted true")
        logger.info("Muted")

    elif name == "unmute":
        _osascript("set volume output muted false")
        logger.info("Unmuted")

    elif name == "volume_up":
        _osascript("set volume output volume ((output volume of (get volume settings)) + 20)")
        logger.info("Volume up")

    elif name == "volume_down":
        _osascript("set volume output volume ((output volume of (get volume settings)) - 20)")
        logger.info("Volume down")

    elif name == "media_pause":
        _osascript('tell application "System Events" to key code 16 using {shift down, command down}')
        logger.info("Media pause/play")

    elif name == "media_next":
        _osascript('tell application "System Events" to key code 124 using {shift down, command down}')
        logger.info("Media next")

    elif name == "media_prev":
        _osascript('tell application "System Events" to key code 123 using {shift down, command down}')
        logger.info("Media prev")

    elif name == "screenshot":
        from pathlib import Path
        dest = str(Path.home() / "Desktop" / "screenshot.png")
        _run(["screencapture", "-iW", dest])
        logger.info("Screenshot → %s", dest)

    elif name == "sleep":
        _osascript('tell application "System Events" to sleep')
        logger.info("Sleep")

    elif name == "lock_screen":
        _osascript('tell application "System Events" to keystroke "q" using {control down, command down}')
        logger.info("Lock screen")

    elif name == "restart":
        if _confirm("Перезагрузить компьютер?"):
            _osascript('tell application "System Events" to restart')
            logger.info("Restart")
        else:
            logger.info("Restart cancelled")

    elif name == "shutdown":
        if _confirm("Выключить компьютер?"):
            _osascript('tell application "System Events" to shut down')
            logger.info("Shutdown")
        else:
            logger.info("Shutdown cancelled")

    elif name == "empty_trash":
        _osascript('tell application "Finder" to empty trash')
        logger.info("Empty trash")

    elif name == "show_desktop":
        _osascript('tell application "System Events" to keystroke "d" using {command down, mission control key down}')
        logger.info("Show desktop")

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
        logger.warning("Unhandled action: %s", name)


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
