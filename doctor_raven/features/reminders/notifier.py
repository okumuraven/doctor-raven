"""Delivers reminders as native desktop notifications via notify-send."""

import shutil
import subprocess


def notify_send_available() -> bool:
    return shutil.which("notify-send") is not None


def notify(title: str, message: str, urgency: str = "normal") -> bool:
    if not notify_send_available():
        return False
    try:
        subprocess.run(
            ["notify-send", "--urgency", urgency, "--app-name", "Doctor Raven", title, message],
            check=True,
            timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
