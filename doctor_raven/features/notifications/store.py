"""Persists a history of every notification-worthy event, regardless of whether a desktop
popup actually fired for it — so a popup you saw (or missed) always has a lookup-able record."""

from doctor_raven.core.db import get_conn
from doctor_raven.features.notifications.models import NotificationEntry


def log_notification(title: str, message: str, source: str) -> NotificationEntry:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO notifications (title, message, source) VALUES (?, ?, ?)",
            (title, message, source),
        )
        row = conn.execute("SELECT * FROM notifications WHERE id = ?", (cur.lastrowid,)).fetchone()
        return NotificationEntry.from_row(row)


def list_recent(limit: int = 20) -> list[NotificationEntry]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM notifications ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [NotificationEntry.from_row(row) for row in rows]
