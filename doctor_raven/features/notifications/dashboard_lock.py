"""Tracks whether a `raven dashboard` process is currently open, via a PID file, so
other processes (e.g. the morning briefing) know to skip a redundant desktop popup
for an event the dashboard is already showing live."""

import os
from pathlib import Path

from doctor_raven.config import ensure_data_dir

LOCK_FILENAME = "dashboard.pid"


def _lock_path() -> Path:
    return ensure_data_dir() / LOCK_FILENAME


def mark_dashboard_running() -> None:
    _lock_path().write_text(str(os.getpid()))


def clear_dashboard_running() -> None:
    _lock_path().unlink(missing_ok=True)


def is_dashboard_running() -> bool:
    lock_path = _lock_path()
    try:
        pid = int(lock_path.read_text().strip())
    except (OSError, ValueError):
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        lock_path.unlink(missing_ok=True)  # stale lock from a crashed/killed dashboard
        return False
    except PermissionError:
        return True  # process exists, just owned by someone else — treat as running
    return True
