"""Audio feedback — macOS uses afplay/osascript, Windows uses winsound/plyer."""
from __future__ import annotations

import logging
import subprocess
import sys
import threading
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class UserFeedback(ABC):
    """Platform-agnostic feedback interface.

    Instantiating ``UserFeedback()`` returns the correct platform backend:
    - macOS: ``_MacFeedback`` using afplay and osascript
    - Windows: ``_WindowsFeedback`` using winsound and plyer
    """

    def __new__(cls) -> "UserFeedback":
        if cls is UserFeedback:
            impl = _WindowsFeedback if sys.platform == "win32" else _MacFeedback
            return super().__new__(impl)
        return super().__new__(cls)

    @abstractmethod
    def notify(self, title: str, message: str) -> None: ...

    @abstractmethod
    def play(self, sound: str) -> None: ...


class _MacFeedback(UserFeedback):
    def notify(self, title: str, message: str) -> None:
        safe_title = title.replace('"', '\\"')
        safe_msg = message.replace('"', '\\"')
        try:
            subprocess.Popen(
                ["osascript", "-e", f'display notification "{safe_msg}" with title "{safe_title}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            logger.exception("Failed to send system notification")

    def play(self, sound: str) -> None:
        try:
            subprocess.Popen(
                ["afplay", f"/System/Library/Sounds/{sound}.aiff"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            logger.exception("Failed to play sound: %s", sound)


class _WindowsFeedback(UserFeedback):
    def notify(self, title: str, message: str) -> None:
        try:
            from plyer import notification  # lazy — Windows only package
            notification.notify(
                title=title,
                message=message,
                app_name="Voice Input",
                timeout=4,
            )
        except Exception:
            logger.exception("Windows notification failed")

    def play(self, sound: str) -> None:
        try:
            import winsound  # lazy — stdlib on Windows, unavailable on macOS
            alias = winsound.MB_ICONHAND if sound == "Funk" else winsound.MB_OK
            threading.Thread(
                target=winsound.MessageBeep,
                args=(alias,),
                daemon=True,
            ).start()
        except Exception:
            logger.exception("Windows sound failed")
