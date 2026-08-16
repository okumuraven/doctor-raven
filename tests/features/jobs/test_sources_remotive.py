import requests

from doctor_raven.features.jobs.sources import remotive


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_maps_fields_to_job_listing(monkeypatch):
    payload = {
        "jobs": [
            {
                "title": "Backend Engineer",
                "company_name": "Acme",
                "url": "https://remotive.com/jobs/1",
                "candidate_required_location": "Worldwide",
                "description": "x" * 2000,
            }
        ]
    }
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(payload))

    listings = remotive.fetch("backend")

    assert len(listings) == 1
    listing = listings[0]
    assert listing.title == "Backend Engineer"
    assert listing.company == "Acme"
    assert listing.source == "Remotive"
    assert listing.location == "Worldwide"
    assert len(listing.description) == 1000


def test_fetch_defaults_missing_location_to_anywhere(monkeypatch):
    payload = {"jobs": [{"title": "Dev", "company_name": "Acme", "url": "https://x", "description": ""}]}
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(payload))

    listings = remotive.fetch("dev")
    assert listings[0].location == "anywhere"


def test_fetch_raises_job_source_unavailable_on_request_failure(monkeypatch):
    def boom(*a, **k):
        raise requests.RequestException("timeout")

    monkeypatch.setattr(requests, "get", boom)

    try:
        remotive.fetch("backend")
        assert False, "expected JobSourceUnavailable"
    except remotive.JobSourceUnavailable:
        pass


def test_fetch_handles_empty_jobs_list(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse({"jobs": []}))
    assert remotive.fetch("nothing") == []
