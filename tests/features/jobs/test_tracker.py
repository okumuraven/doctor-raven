from doctor_raven.features.jobs.models import JobListing, JobMatch
from doctor_raven.features.jobs import tracker


def _match(url: str, title: str = "Software Engineer", company: str = "Acme") -> JobMatch:
    listing = JobListing(
        title=title, company=company, url=url, location="Remote", source="Remotive", description="desc"
    )
    return JobMatch(listing=listing, reason="strong fit")


def test_filter_new_returns_everything_when_nothing_seen(isolated_db):
    matches = [_match("https://a.example/1"), _match("https://a.example/2")]
    assert tracker.filter_new(matches) == matches


def test_record_seen_then_filter_new_excludes_seen_urls(isolated_db):
    seen = _match("https://a.example/1")
    fresh = _match("https://a.example/2")

    tracker.record_seen([seen])
    result = tracker.filter_new([seen, fresh])

    assert result == [fresh]


def test_record_seen_is_idempotent(isolated_db):
    match = _match("https://a.example/1")
    tracker.record_seen([match])
    tracker.record_seen([match])  # must not raise on duplicate URL

    assert tracker.filter_new([match]) == []
