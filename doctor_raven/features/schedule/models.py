"""Task data model for the schedule feature."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    notes: str | None
    due_date: str | None
    priority: str
    status: str
    created_at: str

    @classmethod
    def from_row(cls, row) -> "Task":
        return cls(
            id=row["id"],
            title=row["title"],
            notes=row["notes"],
            due_date=row["due_date"],
            priority=row["priority"],
            status=row["status"],
            created_at=row["created_at"],
        )
