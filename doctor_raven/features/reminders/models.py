"""Reminder data model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Reminder:
    id: int
    message: str
    remind_at: str
    task_id: int | None
    fired: bool
    created_at: str

    @classmethod
    def from_row(cls, row) -> "Reminder":
        return cls(
            id=row["id"],
            message=row["message"],
            remind_at=row["remind_at"],
            task_id=row["task_id"],
            fired=bool(row["fired"]),
            created_at=row["created_at"],
        )
