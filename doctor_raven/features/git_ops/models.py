"""Data model for the git secrets scanner."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SecretFinding:
    file: str
    line: int | None
    kind: str
    preview: str
