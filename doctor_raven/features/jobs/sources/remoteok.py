"""RemoteOK's free public remote-jobs API — no key required. RemoteOK asks that users of
their data credit/link back to remoteok.com, which every listing URL below already does."""

import requests

from doctor_raven.features.jobs.models import JobListing

REMOTEOK_URL = "https://remoteok.com/api"


class JobSourceUnavailable(RuntimeError):
    pass


def fetch(limit: int = 30) -> list[JobListing]:
    try:
        resp = requests.get(REMOTEOK_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise JobSourceUnavailable(f"RemoteOK request failed: {exc}") from exc

    jobs = [job for job in resp.json() if isinstance(job, dict) and "position" in job]
    return [
        JobListing(
            title=job.get("position", "?"),
            company=job.get("company", "?"),
            url=f"https://remoteok.com/remote-jobs/{job.get('id', '')}",
            location=job.get("location") or "anywhere",
            source="RemoteOK",
            description=(job.get("description") or "")[:1000],
        )
        for job in jobs[:limit]
    ]
