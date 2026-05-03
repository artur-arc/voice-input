"""Paste text at the cursor using CGEvent — mirrors OpenSuperWhisper's ClipboardUtil.swift."""
import sys
import time

from AppKit import NSPasteboard, NSPasteboardTypeString, NSArray
from ApplicationServices import AXIsProcessTrustedWithOptions
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    CGEventSourceCreate,
    kCGEventFlagMaskCommand,
    kCGEventSourceStateCombinedSessionState,
    kCGHIDEventTap,
)

# QWERTY keycode for 'v' — works on Russian/non-Latin layouts too
# because CGEvent uses physical key position, not the character
_V_KEYCODE = 9


def has_accessibility() -> bool:
    return bool(AXIsProcessTrustedWithOptions(None))


def accessibility_binary() -> str:
    """Return the executable path that must be added to Accessibility."""
    return sys.executable


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
    """Copy text to clipboard and simulate Cmd+V. Returns True if paste was sent.

    When accessibility is not available the text is left in the clipboard so
    the user can paste it manually with Cmd+V.
    """
    pb = NSPasteboard.generalPasteboard()
    saved = _save_clipboard()

    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)

    if not has_accessibility():
        # Leave text in clipboard for manual paste; old clipboard content is lost.
        return False

    # Use a named event source so the events are marked as synthetic and
    # won't confuse modifier-state tracking in pynput's event tap.
    source = CGEventSourceCreate(kCGEventSourceStateCombinedSessionState)
    key_down = CGEventCreateKeyboardEvent(source, _V_KEYCODE, True)
    key_up = CGEventCreateKeyboardEvent(source, _V_KEYCODE, False)
    CGEventSetFlags(key_down, kCGEventFlagMaskCommand)
    # key_up carries no modifier flags — Cmd is "still held" only for key_down.
    CGEventPost(kCGHIDEventTap, key_down)
    CGEventPost(kCGHIDEventTap, key_up)
    # Wait for the target app to read the clipboard before restoring it.
    time.sleep(0.3)
    _restore_clipboard(saved)
    return True
