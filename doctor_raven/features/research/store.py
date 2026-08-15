"""CRUD operations for research topics, backed by SQLite."""

from doctor_raven.core.db import get_conn
from doctor_raven.features.research.models import Topic


def add_topic(name: str, description: str | None = None) -> Topic:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO topics (name, description) VALUES (?, ?)",
            (name, description),
        )
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (cur.lastrowid,)).fetchone()
        return Topic.from_row(row)


def list_topics(active_only: bool = True) -> list[Topic]:
    query = "SELECT * FROM topics"
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY name"

    with get_conn() as conn:
        rows = conn.execute(query).fetchall()
        return [Topic.from_row(row) for row in rows]


def deactivate_topic(topic_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("UPDATE topics SET active = 0 WHERE id = ?", (topic_id,))
        return cur.rowcount > 0
