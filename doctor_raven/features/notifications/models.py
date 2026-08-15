"""Notification history data model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationEntry:
    id: int
    title: str
    message: str
    source: str
    created_at: str

    @classmethod
    def from_row(cls, row) -> "NotificationEntry":
        return cls(
            id=row["id"],
            title=row["title"],
            message=row["message"],
            source=row["source"],
            created_at=row["created_at"],
        )
