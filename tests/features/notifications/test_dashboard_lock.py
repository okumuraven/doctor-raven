import os

from doctor_raven.features.notifications import dashboard_lock


def test_not_running_when_no_lock_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_lock, "ensure_data_dir", lambda: tmp_path)
    assert dashboard_lock.is_dashboard_running() is False


def test_running_when_lock_holds_a_live_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_lock, "ensure_data_dir", lambda: tmp_path)
    dashboard_lock.mark_dashboard_running()
    assert dashboard_lock.is_dashboard_running() is True


def test_clear_removes_the_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_lock, "ensure_data_dir", lambda: tmp_path)
    dashboard_lock.mark_dashboard_running()
    dashboard_lock.clear_dashboard_running()
    assert dashboard_lock.is_dashboard_running() is False


def test_stale_pid_is_treated_as_not_running_and_cleaned_up(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_lock, "ensure_data_dir", lambda: tmp_path)
    (tmp_path / dashboard_lock.LOCK_FILENAME).write_text("999999999")

    assert dashboard_lock.is_dashboard_running() is False
    assert not (tmp_path / dashboard_lock.LOCK_FILENAME).exists()


def test_malformed_lock_contents_treated_as_not_running(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_lock, "ensure_data_dir", lambda: tmp_path)
    (tmp_path / dashboard_lock.LOCK_FILENAME).write_text("not-a-pid")

    assert dashboard_lock.is_dashboard_running() is False


def test_mark_writes_current_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_lock, "ensure_data_dir", lambda: tmp_path)
    dashboard_lock.mark_dashboard_running()

    assert (tmp_path / dashboard_lock.LOCK_FILENAME).read_text().strip() == str(os.getpid())
