from datetime import date, timedelta

import pytest

from doctor_raven.features.schedule import store


def test_add_task_defaults(isolated_db):
    task = store.add_task("Write tests")
    assert task.id == 1
    assert task.priority == "medium"
    assert task.status == "pending"


def test_add_task_rejects_invalid_priority(isolated_db):
    with pytest.raises(ValueError):
        store.add_task("Bad priority", priority="urgent")


def test_list_tasks_orders_by_priority_then_due_date(isolated_db):
    store.add_task("Low", priority="low")
    store.add_task("High", priority="high")
    store.add_task("Medium", priority="medium")

    assert [t.priority for t in store.list_tasks()] == ["high", "medium", "low"]


def test_list_tasks_excludes_done_by_default(isolated_db):
    task = store.add_task("Finish me")
    store.complete_task(task.id)

    assert store.list_tasks() == []
    assert len(store.list_tasks(include_done=True)) == 1


def test_complete_task_returns_false_for_missing_id(isolated_db):
    assert store.complete_task(999) is False


def test_list_due_today_only_returns_pending_on_or_before_today(isolated_db):
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    store.add_task("Overdue", due_date=yesterday)
    store.add_task("Due today", due_date=today)
    store.add_task("Future", due_date=tomorrow)
    store.add_task("No due date")

    titles = {t.title for t in store.list_due_today()}
    assert titles == {"Overdue", "Due today"}
