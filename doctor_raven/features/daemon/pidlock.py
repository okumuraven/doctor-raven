"""Single-instance guard for the daemon, via a PID file — prevents accidentally running two."""

import os
from pathlib import Path

from doctor_raven.config import ensure_data_dir

LOCK_FILENAME = "daemon.pid"


class DaemonAlreadyRunning(RuntimeError):
    pass


def _lock_path() -> Path:
    return ensure_data_dir() / LOCK_FILENAME


def acquire() -> None:
    lock_path = _lock_path()
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text().strip())
        except ValueError:
            pid = None

        if pid is not None:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass  # stale lock from a crashed/killed daemon — fall through and overwrite
            except PermissionError:
                raise DaemonAlreadyRunning(f"raven daemon already running (pid {pid})")
            else:
                raise DaemonAlreadyRunning(f"raven daemon already running (pid {pid})")

    lock_path.write_text(str(os.getpid()))


def release() -> None:
    _lock_path().unlink(missing_ok=True)
