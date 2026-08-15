import os

import pytest

from doctor_raven.features.daemon import pidlock


def test_acquire_writes_current_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(pidlock, "ensure_data_dir", lambda: tmp_path)
    pidlock.acquire()
    assert (tmp_path / pidlock.LOCK_FILENAME).read_text().strip() == str(os.getpid())


def test_acquire_raises_when_already_running(tmp_path, monkeypatch):
    monkeypatch.setattr(pidlock, "ensure_data_dir", lambda: tmp_path)
    (tmp_path / pidlock.LOCK_FILENAME).write_text(str(os.getpid()))  # our own pid is definitely alive

    with pytest.raises(pidlock.DaemonAlreadyRunning):
        pidlock.acquire()


def test_acquire_overwrites_stale_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(pidlock, "ensure_data_dir", lambda: tmp_path)
    (tmp_path / pidlock.LOCK_FILENAME).write_text("999999999")  # dead pid

    pidlock.acquire()
    assert (tmp_path / pidlock.LOCK_FILENAME).read_text().strip() == str(os.getpid())


def test_release_removes_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(pidlock, "ensure_data_dir", lambda: tmp_path)
    pidlock.acquire()
    pidlock.release()
    assert not (tmp_path / pidlock.LOCK_FILENAME).exists()


def test_release_is_safe_when_no_lock_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(pidlock, "ensure_data_dir", lambda: tmp_path)
    pidlock.release()  # must not raise
