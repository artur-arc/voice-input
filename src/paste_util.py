"""Paste text at the cursor using CGEvent — mirrors OpenSuperWhisper's ClipboardUtil.swift."""
import time

from AppKit import NSPasteboard, NSPasteboardTypeString, NSArray
from ApplicationServices import AXIsProcessTrustedWithOptions
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGSessionEventTap,
)

# QWERTY keycode for 'v' — works on Russian/non-Latin layouts too
# because CGEvent uses physical key position, not the character
_V_KEYCODE = 9


def has_accessibility() -> bool:
    return bool(AXIsProcessTrustedWithOptions(None))


def _save_clipboard() -> list[tuple]:
    pb = NSPasteboard.generalPasteboard()
    saved = []
    for item in pb.pasteboardItems() or []:
        for t in item.types():
            data = item.dataForType_(t)
            if data is not None:
                saved.append((t, data))
    return saved


def _restore_clipboard(saved: list[tuple]) -> None:
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    if not saved:
        return
    from AppKit import NSPasteboardItem
    item = NSPasteboardItem.alloc().init()
    for t, data in saved:
        item.setData_forType_(data, t)
    pb.writeObjects_(NSArray.arrayWithObject_(item))


def paste_text(text: str) -> bool:
    """Copy text to clipboard and simulate Cmd+V. Returns True if paste was sent."""
    pb = NSPasteboard.generalPasteboard()
    saved = _save_clipboard()

    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)

    sent = False
    if has_accessibility():
        key_down = CGEventCreateKeyboardEvent(None, _V_KEYCODE, True)
        key_up = CGEventCreateKeyboardEvent(None, _V_KEYCODE, False)
        CGEventSetFlags(key_down, kCGEventFlagMaskCommand)
        CGEventSetFlags(key_up, kCGEventFlagMaskCommand)
        CGEventPost(kCGSessionEventTap, key_down)
        CGEventPost(kCGSessionEventTap, key_up)
        time.sleep(0.1)
        sent = True

    _restore_clipboard(saved)
    return sent
