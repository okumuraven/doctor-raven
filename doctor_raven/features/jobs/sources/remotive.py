"""Remotive's free public remote-jobs API — no key required, no scraping involved."""

import requests

from doctor_raven.features.jobs.models import JobListing

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"


class JobSourceUnavailable(RuntimeError):
    pass


def fetch(query: str, limit: int = 20) -> list[JobListing]:
    try:
        resp = requests.get(REMOTIVE_URL, params={"search": query, "limit": limit}, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise JobSourceUnavailable(f"Remotive request failed: {exc}") from exc

    jobs = resp.json().get("jobs", [])
    return [
        JobListing(
            title=job.get("title", "?"),
            company=job.get("company_name", "?"),
            url=job.get("url", ""),
            location=job.get("candidate_required_location") or "anywhere",
            source="Remotive",
            description=(job.get("description") or "")[:1000],
        )
        for job in jobs
    ]
