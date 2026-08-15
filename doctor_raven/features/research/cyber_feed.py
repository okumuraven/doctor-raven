"""Recently added actively-exploited CVEs via CISA's Known Exploited Vulnerabilities (KEV)
catalog — public, no auth required."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import requests

KEV_FEED_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


class KevFeedUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class KevEntry:
    cve_id: str
    vendor: str
    product: str
    name: str
    date_added: str


def fetch_recent_kev(lookback_days: int = 3, limit: int = 8) -> list[KevEntry]:
    try:
        resp = requests.get(KEV_FEED_URL, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise KevFeedUnavailable(f"CISA KEV feed request failed: {exc}") from exc

    cutoff = date.today() - timedelta(days=lookback_days)
    entries = []
    for vuln in resp.json().get("vulnerabilities", []):
        added_str = vuln.get("dateAdded")
        try:
            added = datetime.strptime(added_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        if added < cutoff:
            continue
        entries.append(
            KevEntry(
                cve_id=vuln.get("cveID", "?"),
                vendor=vuln.get("vendorProject", "?"),
                product=vuln.get("product", "?"),
                name=vuln.get("vulnerabilityName", "?"),
                date_added=added_str,
            )
        )

    entries.sort(key=lambda e: e.date_added, reverse=True)
    return entries[:limit]
