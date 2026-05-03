"""Paste text at the cursor using CGEvent — mirrors OpenSuperWhisper's ClipboardUtil.swift."""
import sys

from AppKit import NSPasteboard, NSPasteboardTypeString
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

_V_KEYCODE = 9


def has_accessibility() -> bool:
    return bool(AXIsProcessTrustedWithOptions(None))


def accessibility_binary() -> str:
    return sys.executable


def paste_text(text: str) -> bool:
    """Copy text to clipboard and simulate Cmd+V. Returns True if paste was sent."""
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)

    if not has_accessibility():
        return False

    source = CGEventSourceCreate(kCGEventSourceStateCombinedSessionState)
    key_down = CGEventCreateKeyboardEvent(source, _V_KEYCODE, True)
    key_up = CGEventCreateKeyboardEvent(source, _V_KEYCODE, False)
    CGEventSetFlags(key_down, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, key_down)
    CGEventPost(kCGHIDEventTap, key_up)
    return True
