"""Paste text at cursor — macOS uses CGEvent/NSPasteboard, Windows uses SendInput/ctypes clipboard."""
from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

# ── macOS ─────────────────────────────────────────────────────────────────────

if sys.platform != "win32":
    from AppKit import NSPasteboard, NSPasteboardTypeString
    from ApplicationServices import AXIsProcessTrustedWithOptions
    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        CGEventSourceCreate,
        kCGAnnotatedSessionEventTap,
        kCGEventFlagMaskCommand,
        kCGEventSourceStateCombinedSessionState,
    )

    _V_KEYCODE: int = 9  # macOS virtual key code for V

# ── Windows ───────────────────────────────────────────────────────────────────

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _WIN_INPUT_KEYBOARD: int = 1
    _WIN_KEYEVENTF_KEYUP: int = 0x0002
    _WIN_VK_CONTROL: int = 0x11
    _WIN_VK_V: int = 0x56

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class _INPUT(ctypes.Structure):
        class _I(ctypes.Union):
            _fields_ = [("ki", _KEYBDINPUT)]
        _anonymous_ = ("_i",)
        _fields_ = [("type", wintypes.DWORD), ("_i", _I)]

# ── Public API ────────────────────────────────────────────────────────────────


def has_accessibility() -> bool:
    if sys.platform == "win32":
        return True  # Windows has no TCC permission model for SendInput
    return bool(AXIsProcessTrustedWithOptions(None))


def accessibility_binary() -> str:
    return sys.executable


def paste_text(text: str) -> bool:
    """Copy text to clipboard and simulate the paste shortcut (Cmd+V on macOS, Ctrl+V on Windows)."""
    if sys.platform == "win32":
        return _win_paste(text)
    return _mac_paste(text)


# ── macOS implementation ──────────────────────────────────────────────────────


def _mac_paste(text: str) -> bool:
    try:
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(text, NSPasteboardTypeString)
    except Exception:
        logger.exception("Failed to write text to clipboard")
        return False

    if not has_accessibility():
        return False

    try:
        source = CGEventSourceCreate(kCGEventSourceStateCombinedSessionState)
        key_down = CGEventCreateKeyboardEvent(source, _V_KEYCODE, True)
        key_up = CGEventCreateKeyboardEvent(source, _V_KEYCODE, False)
        CGEventSetFlags(key_down, kCGEventFlagMaskCommand)
        CGEventPost(kCGAnnotatedSessionEventTap, key_down)
        CGEventPost(kCGAnnotatedSessionEventTap, key_up)
        return True
    except Exception:
        logger.exception("CGEvent paste failed")
        return False


# ── Windows implementation ────────────────────────────────────────────────────


def _win_paste(text: str) -> bool:
    try:
        _win_write_clipboard(text)
        _win_send_ctrl_v()
        return True
    except Exception:
        logger.warning("Ctrl+V paste failed — falling back to keyboard.write()")
        return _win_keyboard_write(text)


def _win_write_clipboard(text: str) -> None:
    # Pure ctypes — no pywin32 required.
    import ctypes
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    encoded = (text + "\x00").encode("utf-16-le")
    h = ctypes.windll.kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    ptr = ctypes.windll.kernel32.GlobalLock(h)
    ctypes.memmove(ptr, encoded, len(encoded))
    ctypes.windll.kernel32.GlobalUnlock(h)
    if not ctypes.windll.user32.OpenClipboard(0):
        raise OSError("OpenClipboard failed")
    try:
        ctypes.windll.user32.EmptyClipboard()
        ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        ctypes.windll.user32.CloseClipboard()


def _win_keyboard_write(text: str) -> bool:
    try:
        import keyboard  # type: ignore[import]
        keyboard.write(text, delay=0.008)
        return True
    except Exception:
        logger.exception("keyboard.write fallback failed")
        return False


def _win_send_ctrl_v() -> None:
    inputs = [
        _INPUT(type=_WIN_INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=_WIN_VK_CONTROL)),
        _INPUT(type=_WIN_INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=_WIN_VK_V)),
        _INPUT(type=_WIN_INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=_WIN_VK_V, dwFlags=_WIN_KEYEVENTF_KEYUP)),
        _INPUT(type=_WIN_INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=_WIN_VK_CONTROL, dwFlags=_WIN_KEYEVENTF_KEYUP)),
    ]
    n = len(inputs)
    ctypes.windll.user32.SendInput(n, (_INPUT * n)(*inputs), ctypes.sizeof(_INPUT))
