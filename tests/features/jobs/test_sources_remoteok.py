import requests

from doctor_raven.features.jobs.sources import remoteok


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_skips_leading_legend_entry_and_maps_fields(monkeypatch):
    payload = [
        {"legal": "notice"},  # RemoteOK's real API prepends a non-job legend object
        {
            "position": "Frontend Engineer",
            "company": "Acme",
            "id": "123",
            "location": "Remote",
            "description": "x" * 2000,
        },
    ]
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(payload))

    listings = remoteok.fetch()

    assert len(listings) == 1
    listing = listings[0]
    assert listing.title == "Frontend Engineer"
    assert listing.company == "Acme"
    assert listing.source == "RemoteOK"
    assert listing.url == "https://remoteok.com/remote-jobs/123"
    assert len(listing.description) == 1000


def test_fetch_defaults_missing_location_to_anywhere(monkeypatch):
    payload = [{"position": "Dev", "company": "Acme", "id": "1", "description": ""}]
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(payload))

    listings = remoteok.fetch()
    assert listings[0].location == "anywhere"


def test_fetch_respects_limit(monkeypatch):
    payload = [{"position": f"Dev {i}", "company": "Acme", "id": str(i), "description": ""} for i in range(5)]
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(payload))

    listings = remoteok.fetch(limit=2)
    assert len(listings) == 2


def test_fetch_raises_job_source_unavailable_on_request_failure(monkeypatch):
    def boom(*a, **k):
        raise requests.RequestException("timeout")

    monkeypatch.setattr(requests, "get", boom)

    try:
        remoteok.fetch()
        assert False, "expected JobSourceUnavailable"
    except remoteok.JobSourceUnavailable:
        pass
