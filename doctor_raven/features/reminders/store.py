"""CRUD operations for reminders, backed by SQLite."""

from datetime import datetime

from doctor_raven.core.db import get_conn
from doctor_raven.features.reminders.models import Reminder


def add_reminder(message: str, remind_at: str, task_id: int | None = None) -> Reminder:
    with get_conn() as conn:
        if task_id is not None:
            exists = conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not exists:
                raise ValueError(f"task_id {task_id} does not exist")

        cur = conn.execute(
            "INSERT INTO reminders (message, remind_at, task_id) VALUES (?, ?, ?)",
            (message, remind_at, task_id),
        )
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (cur.lastrowid,)).fetchone()
        return Reminder.from_row(row)


def list_reminders(include_fired: bool = False) -> list[Reminder]:
    query = "SELECT * FROM reminders"
    if not include_fired:
        query += " WHERE fired = 0"
    query += " ORDER BY remind_at"

    with get_conn() as conn:
        rows = conn.execute(query).fetchall()
        return [Reminder.from_row(row) for row in rows]


def list_due(now: str | None = None) -> list[Reminder]:
    now = now or datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE fired = 0 AND remind_at <= ? ORDER BY remind_at",
            (now,),
        ).fetchall()
        return [Reminder.from_row(row) for row in rows]


def mark_fired(reminder_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE reminders SET fired = 1 WHERE id = ?", (reminder_id,))
