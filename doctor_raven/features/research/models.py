"""Topic data model for the research/brainstorm feature."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    id: int
    name: str
    description: str | None
    active: bool
    created_at: str

    @classmethod
    def from_row(cls, row) -> "Topic":
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            active=bool(row["active"]),
            created_at=row["created_at"],
        )
