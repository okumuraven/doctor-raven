import pytest

from doctor_raven.features.reminders import store
from doctor_raven.features.schedule import store as task_store


def test_add_reminder_without_task_id(isolated_db):
    reminder = store.add_reminder("Check backups", "2026-08-20T09:00")
    assert reminder.task_id is None
    assert reminder.fired is False


def test_add_reminder_rejects_nonexistent_task_id(isolated_db):
    with pytest.raises(ValueError):
        store.add_reminder("Bad link", "2026-08-20T09:00", task_id=999)


def test_add_reminder_with_valid_task_id(isolated_db):
    task = task_store.add_task("Some task")
    reminder = store.add_reminder("Follow up", "2026-08-20T09:00", task_id=task.id)
    assert reminder.task_id == task.id


def test_list_due_returns_only_unfired_at_or_before_now(isolated_db):
    store.add_reminder("Past", "2020-01-01T00:00")
    store.add_reminder("Future", "2099-01-01T00:00")

    due = store.list_due(now="2026-01-01T00:00")
    assert [r.message for r in due] == ["Past"]


def test_mark_fired_excludes_from_default_list(isolated_db):
    reminder = store.add_reminder("One-off", "2020-01-01T00:00")
    store.mark_fired(reminder.id)

    assert store.list_reminders() == []
    assert len(store.list_reminders(include_fired=True)) == 1
