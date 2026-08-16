"""Dedup store for the daemon's job sweep — a matching listing only triggers a notification
the first time it's seen, never again on subsequent sweeps."""

from doctor_raven.core.db import get_conn
from doctor_raven.features.jobs.models import JobMatch


def filter_new(matches: list[JobMatch]) -> list[JobMatch]:
    new_matches = []
    with get_conn() as conn:
        for match in matches:
            row = conn.execute("SELECT 1 FROM seen_jobs WHERE url = ?", (match.listing.url,)).fetchone()
            if row is None:
                new_matches.append(match)
    return new_matches


def record_seen(matches: list[JobMatch]) -> None:
    with get_conn() as conn:
        for match in matches:
            conn.execute(
                "INSERT OR IGNORE INTO seen_jobs (url, title, company) VALUES (?, ?, ?)",
                (match.listing.url, match.listing.title, match.listing.company),
            )
