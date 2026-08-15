"""Recent software/tech headlines via the Hacker News Algolia API (public, no auth required)."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"


class TechFeedUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class TechStory:
    title: str
    url: str | None
    points: int
    created_at: str


def fetch_recent_stories(lookback_days: int = 3, limit: int = 8) -> list[TechStory]:
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=lookback_days)).timestamp())
    params = {"tags": "story", "numericFilters": f"created_at_i>{cutoff}", "hitsPerPage": 50}

    try:
        resp = requests.get(HN_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise TechFeedUnavailable(f"Hacker News API request failed: {exc}") from exc

    hits = resp.json().get("hits", [])
    stories = [
        TechStory(
            title=hit["title"],
            url=hit.get("url"),
            points=hit.get("points") or 0,
            created_at=hit.get("created_at") or "",
        )
        for hit in hits
        if hit.get("title")
    ]
    stories.sort(key=lambda s: s.points, reverse=True)
    return stories[:limit]
