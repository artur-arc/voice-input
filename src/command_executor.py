"""Voice command executor: simple pattern matching + Ollama fallback."""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
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

# ── Windows helpers ──────────────────────────────────────────────────────────

# Virtual key codes for media / volume
_WIN_VK_MUTE       = 0xAD
_WIN_VK_VOL_DOWN   = 0xAE
_WIN_VK_VOL_UP     = 0xAF
_WIN_VK_MEDIA_NEXT = 0xB0
_WIN_VK_MEDIA_PREV = 0xB1
_WIN_VK_MEDIA_STOP = 0xB2
_WIN_VK_MEDIA_PLAY = 0xB3
_WIN_VK_LWIN       = 0x5B
_WIN_VK_D          = 0x44
_KEYEVENTF_KEYUP   = 0x0002


def _win_vk_press(vk: int) -> None:
    import ctypes
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


def _win_open(target: str) -> None:
    """Open URL, protocol URI, or file path via ShellExecute."""
    os.startfile(target)


def _win_exe(exe: str, *args: str) -> None:
    """Launch an executable by name (must be on PATH or a known alias)."""
    try:
        subprocess.Popen([exe, *args])
    except FileNotFoundError:
        logger.warning("Executable not found: %s", exe)


def _win_screenshot() -> None:
    from pathlib import Path
    from PIL import ImageGrab
    dest = Path.home() / "Desktop" / "screenshot.png"
    img = ImageGrab.grab()
    img.save(dest)
    logger.info("Screenshot → %s", dest)


def _win_speak(text: str, lang: str = "ru") -> None:
    safe = text.replace("'", "''")
    subprocess.Popen([
        "powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
        f"Add-Type -AssemblyName System.Speech; "
        f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Speak('{safe}')",
    ])
    logger.info("Speaking (SAPI): %s", text[:80])


def _win_confirm(message: str) -> bool:
    import ctypes
    # MB_OKCANCEL = 0x1; returns 1 (IDOK) or 2 (IDCANCEL)
    return ctypes.windll.user32.MessageBoxW(0, message, "Voice Input", 0x1) == 1


# Windows app name → launcher target (exe name or protocol URI)
_WIN_APP_MAP: dict[str, str] = {
    "safari":          "__default_browser__",
    "сафари":          "__default_browser__",
    "браузер":         "__default_browser__",
    "browser":         "__default_browser__",
    "chrome":          "chrome",
    "google chrome":   "chrome",
    "хром":            "chrome",
    "firefox":         "firefox",
    "фаерфокс":        "firefox",
    "spotify":         "__spotify__",
    "спотифай":        "__spotify__",
    "спотифи":         "__spotify__",
    "music":           "wmplayer",
    "itunes":          "wmplayer",
    "итюнс":           "wmplayer",
    "музыка":          "wmplayer",
    "terminal":        "wt",
    "терминал":        "wt",
    "finder":          "explorer",
    "файлы":           "explorer",
    "проводник":       "explorer",
    "notes":           "notepad",
    "заметки":         "notepad",
    "settings":        "ms-settings:",
    "system settings": "ms-settings:",
    "настройки":       "ms-settings:",
    "vscode":          "code",
    "vs code":         "code",
    "visual studio":   "code",
    "slack":           "slack",
    "слак":            "slack",
    "telegram":        "telegram",
    "телеграм":        "telegram",
    "zoom":            "zoom",
}

# ── macOS app name lookup (for Ollama open_app responses) ─────────────────────

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
You are a voice assistant for macOS and Windows. The user speaks in Russian, English, or Hebrew.
Decide if the input is a COMMAND or a QUESTION, then return ONLY a JSON object.

For COMMANDS use {"type": "command", "action": "...", ...}:
{"type": "command", "action": "open_browser"}
{"type": "command", "action": "open_spotify"}
{"type": "command", "action": "open_safari"}
{"type": "command", "action": "open_chrome"}
{"type": "command", "action": "open_music"}
{"type": "command", "action": "open_terminal"}
{"type": "command", "action": "open_finder"}
{"type": "command", "action": "open_notes"}
{"type": "command", "action": "open_settings"}
{"type": "command", "action": "open_slack"}
{"type": "command", "action": "open_telegram"}
{"type": "command", "action": "open_zoom"}
{"type": "command", "action": "open_downloads"}
{"type": "command", "action": "open_documents"}
{"type": "command", "action": "mute"}
{"type": "command", "action": "unmute"}
{"type": "command", "action": "volume_up"}
{"type": "command", "action": "volume_down"}
{"type": "command", "action": "media_pause"}
{"type": "command", "action": "media_next"}
{"type": "command", "action": "media_prev"}
{"type": "command", "action": "screenshot"}
{"type": "command", "action": "sleep"}
{"type": "command", "action": "lock_screen"}
{"type": "command", "action": "restart"}
{"type": "command", "action": "shutdown"}
{"type": "command", "action": "empty_trash"}
{"type": "command", "action": "show_desktop"}
{"type": "command", "action": "google_search", "query": "..."}
{"type": "command", "action": "youtube_search", "query": "..."}
{"type": "command", "action": "open_url", "url": "https://..."}
{"type": "command", "action": "open_app", "app": "AppName"}

For QUESTIONS use {"type": "answer", "text": "..."}:
- Answer in the SAME language as the question
- Be concise: 1-3 sentences max (it will be spoken aloud)
- If you don't know or need real-time data, say so briefly

Examples:
"открой браузер" → {"type": "command", "action": "open_browser"}
"найди iPhone 17" → {"type": "command", "action": "google_search", "query": "iPhone 17"}
"сколько планет в солнечной системе?" → {"type": "answer", "text": "В Солнечной системе 8 планет."}
"что такое машинное обучение?" → {"type": "answer", "text": "Машинное обучение — это раздел ИИ, где алгоритмы обучаются на данных без явного программирования."}
"what is the capital of France?" → {"type": "answer", "text": "The capital of France is Paris."}

Return ONLY the JSON object.
"""


def _run(cmd: list[str]) -> None:
    subprocess.Popen(cmd)


def _osascript(script: str) -> None:
    subprocess.run(["osascript", "-e", script], check=False)


# macOS TTS voices per language
_TTS_VOICE: dict[str, str] = {
    "ru": "Milena",
    "en": "Samantha",
    "he": "Carmit",
}


def _speak(text: str, lang: str = "ru") -> None:
    if sys.platform == "win32":
        _win_speak(text, lang)
        return
    voice = _TTS_VOICE.get(lang, "Samantha")
    subprocess.Popen(["say", "-v", voice, text])
    logger.info("Speaking [%s]: %s", voice, text[:80])


def _press_space_after(delay: float) -> None:
    """Press Space after a delay to trigger Spotify play (macOS only)."""
    if sys.platform == "win32":
        def _do():
            time.sleep(delay)
            _win_vk_press(_WIN_VK_MEDIA_PLAY)
        threading.Thread(target=_do, daemon=True).start()
        return

    def _do():
        time.sleep(delay)
        subprocess.run(
            ["osascript", "-e", "tell application \"System Events\" to key code 49"],
            check=False,
        )
    threading.Thread(target=_do, daemon=True).start()


def _confirm(message: str) -> bool:
    if sys.platform == "win32":
        return _win_confirm(message)
    result = subprocess.run(
        ["osascript", "-e",
         f'display dialog "{message}" buttons {{"Отмена", "OK"}} default button "Отмена"'],
        capture_output=True,
    )
    return result.returncode == 0


def _resolve_app_name(name: str) -> str:
    m = _WIN_APP_MAP if sys.platform == "win32" else _APP_MAP
    return m.get(name.lower().strip(), name)


def _execute(action: dict) -> None:  # noqa: C901
    if sys.platform == "win32":
        _execute_win(action)
    else:
        _execute_mac(action)


def _execute_mac(action: dict) -> None:  # noqa: C901
    name = action.get("action", "unknown")

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


def _execute_win(action: dict) -> None:  # noqa: C901
    import ctypes
    from pathlib import Path

    name = action.get("action", "unknown")

    _WIN_EXE_CMDS: dict[str, str] = {
        "open_chrome":   "chrome",
        "open_firefox":  "firefox",
        "open_music":    "wmplayer",
        "open_terminal": "wt",
        "open_finder":   "explorer",
        "open_notes":    "notepad",
        "open_vscode":   "code",
        "open_slack":    "slack",
        "open_telegram": "telegram",
        "open_zoom":     "zoom",
    }

    if name == "open_browser":
        _win_open("https://www.google.com")
        logger.info("Opened default browser")

    elif name == "open_safari":
        # Safari doesn't exist on Windows — open default browser
        _win_open("https://www.google.com")
        logger.info("Opened default browser (Safari unavailable on Windows)")

    elif name == "open_spotify":
        _win_open("https://open.spotify.com/")
        _press_space_after(4.0)
        logger.info("Opened Spotify web player")

    elif name in _WIN_EXE_CMDS:
        _win_exe(_WIN_EXE_CMDS[name])
        logger.info("Executed: %s", name)

    elif name == "open_settings":
        _win_open("ms-settings:")
        logger.info("Opened Settings")

    elif name == "open_downloads":
        _win_open(str(Path.home() / "Downloads"))
        logger.info("Opened Downloads")

    elif name == "open_documents":
        _win_open(str(Path.home() / "Documents"))
        logger.info("Opened Documents")

    elif name == "open_desktop":
        _win_open(str(Path.home() / "Desktop"))
        logger.info("Opened Desktop")

    elif name == "open_app":
        app = _resolve_app_name(action.get("app", ""))
        if app == "__default_browser__":
            _win_open("https://www.google.com")
        elif app == "__spotify__":
            _win_open("https://open.spotify.com/")
        elif app.endswith(":"):
            _win_open(app)
        else:
            _win_exe(app)
        logger.info("Opened app: %s", app)

    elif name == "mute":
        _win_vk_press(_WIN_VK_MUTE)
        logger.info("Muted")

    elif name == "unmute":
        _win_vk_press(_WIN_VK_MUTE)
        logger.info("Unmuted (toggled mute)")

    elif name == "volume_up":
        for _ in range(10):
            _win_vk_press(_WIN_VK_VOL_UP)
        logger.info("Volume up")

    elif name == "volume_down":
        for _ in range(10):
            _win_vk_press(_WIN_VK_VOL_DOWN)
        logger.info("Volume down")

    elif name == "media_pause":
        _win_vk_press(_WIN_VK_MEDIA_PLAY)
        logger.info("Media pause/play")

    elif name == "media_next":
        _win_vk_press(_WIN_VK_MEDIA_NEXT)
        logger.info("Media next")

    elif name == "media_prev":
        _win_vk_press(_WIN_VK_MEDIA_PREV)
        logger.info("Media prev")

    elif name == "screenshot":
        _win_screenshot()

    elif name == "sleep":
        subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        logger.info("Sleep")

    elif name == "lock_screen":
        ctypes.windll.user32.LockWorkStation()
        logger.info("Lock screen")

    elif name == "restart":
        if _confirm("Перезагрузить компьютер?"):
            subprocess.run(["shutdown", "/r", "/t", "0"], check=False)
            logger.info("Restart")
        else:
            logger.info("Restart cancelled")

    elif name == "shutdown":
        if _confirm("Выключить компьютер?"):
            subprocess.run(["shutdown", "/s", "/t", "0"], check=False)
            logger.info("Shutdown")
        else:
            logger.info("Shutdown cancelled")

    elif name == "empty_trash":
        # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x0007)
        logger.info("Empty Recycle Bin")

    elif name == "show_desktop":
        ctypes.windll.user32.keybd_event(_WIN_VK_LWIN, 0, 0, 0)
        ctypes.windll.user32.keybd_event(_WIN_VK_D, 0, 0, 0)
        ctypes.windll.user32.keybd_event(_WIN_VK_D, 0, _KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(_WIN_VK_LWIN, 0, _KEYEVENTF_KEYUP, 0)
        logger.info("Show desktop")

    elif name == "google_search":
        query = action.get("query", "")
        _win_open(f"https://www.google.com/search?q={quote_plus(query)}")
        logger.info("Google search: %s", query)

    elif name == "youtube_search":
        query = action.get("query", "")
        _win_open(f"https://www.youtube.com/search?query={quote_plus(query)}")
        logger.info("YouTube search: %s", query)

    elif name == "open_url":
        _win_open(action.get("url", ""))
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
        "prompt": f'Input: "{text}"\nJSON:',
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 200},
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
            parsed = json.loads(result.get("response", "{}"))
            if parsed.get("action") == "open_app":
                resolved = _resolve_app_name(parsed.get("app", ""))
                if resolved != parsed.get("app"):
                    parsed["app"] = resolved
            return parsed
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        logger.error("Ollama error: %s", exc)
        return {"type": "command", "action": "unknown"}


def handle(text: str, lang: str = "ru") -> bool:
    """Handle voice input: execute command or answer question via TTS."""
    if _try_simple(text):
        return True

    logger.info("Sending to Ollama: %s", text)
    result = _ask_ollama(text)
    logger.info("Ollama result: %s", result)

    kind = result.get("type", "command")

    if kind == "answer":
        answer = result.get("text", "")
        if answer:
            _speak(answer, lang)
            return True
        return False

    # Command
    action = dict(result)
    action.pop("type", None)
    if action.get("action") == "unknown":
        logger.warning("Not understood: %s", text)
        return False

    _execute(action)
    return True
