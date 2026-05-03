import logging
import subprocess

logger = logging.getLogger(__name__)


class UserFeedback:
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
