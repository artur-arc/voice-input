"""Paste text at cursor — macOS uses CGEvent/NSPasteboard, Windows uses SendInput/ctypes clipboard."""
from __future__ import annotations

import ctypes
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
        logger.warning("Ctrl+V paste failed — trying pyperclip fallback")
    try:
        import pyperclip
        pyperclip.copy(text)
        _win_send_ctrl_v()
        return True
    except Exception:
        logger.warning("pyperclip fallback failed — trying keyboard.write()")
    return _win_keyboard_write(text)


def _win_write_clipboard(text: str) -> None:
    # Pure ctypes — no pywin32 required.
    # restype must be c_void_p for pointer-returning functions on 64-bit Windows;
    # the default c_int silently truncates 64-bit addresses.
    import ctypes
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    k32 = ctypes.windll.kernel32
    u32 = ctypes.windll.user32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.restype = ctypes.c_void_p
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

    encoded = (text + "\x00").encode("utf-16-le")
    h = k32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    if not h:
        raise OSError("GlobalAlloc failed")
    ptr = k32.GlobalLock(h)
    if not ptr:
        raise OSError("GlobalLock failed")
    ctypes.memmove(ptr, encoded, len(encoded))
    k32.GlobalUnlock(h)

    if not u32.OpenClipboard(0):
        raise OSError("OpenClipboard failed")
    try:
        u32.EmptyClipboard()
        if not u32.SetClipboardData(CF_UNICODETEXT, h):
            raise OSError("SetClipboardData failed")
    finally:
        u32.CloseClipboard()


def _win_keyboard_write(text: str) -> bool:
    try:
        import keyboard  # type: ignore[import]
        keyboard.write(text, delay=0.008)
        return True
    except Exception:
        logger.exception("All paste methods failed")
        return False


def _win_send_ctrl_v() -> None:
    from ctypes import wintypes

    INPUT_KEYBOARD  = 1
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL      = 0x11
    VK_V            = 0x56

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk",        wintypes.WORD),
            ("wScan",      wintypes.WORD),
            ("dwFlags",    wintypes.DWORD),
            ("time",       wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class _INPUT(ctypes.Structure):
        class _I(ctypes.Union):
            _fields_ = [("ki", _KEYBDINPUT)]
        _anonymous_ = ("_i",)
        _fields_ = [("type", wintypes.DWORD), ("_i", _I)]

    inputs = [
        _INPUT(type=INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=VK_CONTROL)),
        _INPUT(type=INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=VK_V)),
        _INPUT(type=INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=VK_V,        dwFlags=KEYEVENTF_KEYUP)),
        _INPUT(type=INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=VK_CONTROL,  dwFlags=KEYEVENTF_KEYUP)),
    ]
    n = len(inputs)
    ctypes.windll.user32.SendInput(n, (_INPUT * n)(*inputs), ctypes.sizeof(_INPUT))
