from datetime import date, timedelta

import pytest
import requests as real_requests

from doctor_raven.features.research import cyber_feed


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_filters_by_lookback_window(monkeypatch):
    today = date.today()
    recent = (today - timedelta(days=1)).isoformat()
    old = (today - timedelta(days=30)).isoformat()
    payload = {
        "vulnerabilities": [
            {"cveID": "CVE-RECENT", "vendorProject": "V", "product": "P", "vulnerabilityName": "N", "dateAdded": recent},
            {"cveID": "CVE-OLD", "vendorProject": "V", "product": "P", "vulnerabilityName": "N", "dateAdded": old},
        ]
    }
    monkeypatch.setattr(cyber_feed.requests, "get", lambda *a, **k: FakeResponse(payload))

    entries = cyber_feed.fetch_recent_kev(lookback_days=7)
    assert [e.cve_id for e in entries] == ["CVE-RECENT"]


def test_skips_entries_with_malformed_dates(monkeypatch):
    payload = {"vulnerabilities": [{"cveID": "CVE-BAD", "dateAdded": "not-a-date"}]}
    monkeypatch.setattr(cyber_feed.requests, "get", lambda *a, **k: FakeResponse(payload))

    assert cyber_feed.fetch_recent_kev() == []


def test_raises_kev_feed_unavailable_on_request_failure(monkeypatch):
    def boom(*a, **k):
        raise real_requests.RequestException("down")

    monkeypatch.setattr(cyber_feed.requests, "get", boom)

    with pytest.raises(cyber_feed.KevFeedUnavailable):
        cyber_feed.fetch_recent_kev()
