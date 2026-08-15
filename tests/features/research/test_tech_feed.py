import pytest
import requests as real_requests

from doctor_raven.features.research import tech_feed


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_sorts_by_points_and_respects_limit(monkeypatch):
    hits = [
        {"title": "Low", "url": "http://a", "points": 1, "created_at": "2026-08-14T00:00:00Z"},
        {"title": "High", "url": "http://b", "points": 50, "created_at": "2026-08-14T00:00:00Z"},
        {"title": "Mid", "url": "http://c", "points": 10, "created_at": "2026-08-14T00:00:00Z"},
    ]
    monkeypatch.setattr(tech_feed.requests, "get", lambda *a, **k: FakeResponse({"hits": hits}))

    stories = tech_feed.fetch_recent_stories(limit=2)
    assert [s.title for s in stories] == ["High", "Mid"]


def test_skips_hits_without_title(monkeypatch):
    hits = [{"title": None, "points": 100}, {"title": "Kept", "points": 5, "url": None, "created_at": ""}]
    monkeypatch.setattr(tech_feed.requests, "get", lambda *a, **k: FakeResponse({"hits": hits}))

    assert [s.title for s in tech_feed.fetch_recent_stories()] == ["Kept"]


def test_raises_tech_feed_unavailable_on_request_failure(monkeypatch):
    def boom(*a, **k):
        raise real_requests.RequestException("network down")

    monkeypatch.setattr(tech_feed.requests, "get", boom)

    with pytest.raises(tech_feed.TechFeedUnavailable):
        tech_feed.fetch_recent_stories()
