"""CRUD operations for tasks, backed by SQLite."""

from datetime import date

from doctor_raven.core.db import get_conn
from doctor_raven.features.schedule.models import Task

VALID_PRIORITIES = ("low", "medium", "high")


def add_task(title: str, notes: str | None = None, due_date: str | None = None, priority: str = "medium") -> Task:
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"priority must be one of {VALID_PRIORITIES}, got '{priority}'")

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, notes, due_date, priority) VALUES (?, ?, ?, ?)",
            (title, notes, due_date, priority),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        return Task.from_row(row)


def list_tasks(include_done: bool = False) -> list[Task]:
    query = "SELECT * FROM tasks"
    if not include_done:
        query += " WHERE status = 'pending'"
    query += " ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, due_date IS NULL, due_date"

    with get_conn() as conn:
        rows = conn.execute(query).fetchall()
        return [Task.from_row(row) for row in rows]


def list_due_today() -> list[Task]:
    today = date.today().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = 'pending' AND due_date <= ? ORDER BY due_date",
            (today,),
        ).fetchall()
        return [Task.from_row(row) for row in rows]


def complete_task(task_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,))
        return cur.rowcount > 0
