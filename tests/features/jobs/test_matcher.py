from doctor_raven.core import llm_router
from doctor_raven.features.jobs import matcher
from doctor_raven.features.jobs.models import JobListing


class FakeConfig:
    pass


def _listing(title: str, url: str) -> JobListing:
    return JobListing(title=title, company="Acme", url=url, location="Remote", source="Remotive", description="desc")


def test_score_returns_empty_list_when_no_listings():
    assert matcher.score([], "resume text", FakeConfig()) == []


def test_score_parses_valid_json_response(monkeypatch):
    listings = [_listing("Software Engineer", "https://a/1"), _listing("Facilities Planner", "https://a/2")]
    monkeypatch.setattr(
        llm_router, "complete", lambda *a, **k: '[{"index": 0, "reason": "matches Python/React background"}]'
    )

    matches = matcher.score(listings, "resume text", FakeConfig())

    assert len(matches) == 1
    assert matches[0].listing.title == "Software Engineer"
    assert matches[0].reason == "matches Python/React background"


def test_score_strips_markdown_code_fences(monkeypatch):
    listings = [_listing("Software Engineer", "https://a/1")]
    monkeypatch.setattr(
        llm_router, "complete", lambda *a, **k: '```json\n[{"index": 0, "reason": "fit"}]\n```'
    )

    matches = matcher.score(listings, "resume text", FakeConfig())
    assert len(matches) == 1


def test_score_returns_empty_list_on_invalid_json(monkeypatch):
    listings = [_listing("Software Engineer", "https://a/1")]
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "not json at all")

    assert matcher.score(listings, "resume text", FakeConfig()) == []


def test_score_ignores_out_of_range_index(monkeypatch):
    listings = [_listing("Software Engineer", "https://a/1")]
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: '[{"index": 5, "reason": "bogus"}]')

    assert matcher.score(listings, "resume text", FakeConfig()) == []


def test_score_accepts_bare_index_list_from_less_compliant_models(monkeypatch):
    """Smaller local models (e.g. llama3.2) sometimes ignore the {"index", "reason"} shape and
    emit a bare list of ints instead — a real match should still surface, just unlabeled."""
    listings = [_listing("Software Engineer", "https://a/1"), _listing("Facilities Planner", "https://a/2")]
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "[0]")

    matches = matcher.score(listings, "resume text", FakeConfig())

    assert len(matches) == 1
    assert matches[0].listing.title == "Software Engineer"
    assert matches[0].reason == ""


def test_score_ignores_non_list_json(monkeypatch):
    listings = [_listing("Software Engineer", "https://a/1")]
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: '{"index": 0}')

    assert matcher.score(listings, "resume text", FakeConfig()) == []


def test_score_returns_empty_list_when_no_llm_available(monkeypatch):
    listings = [_listing("Software Engineer", "https://a/1")]

    def boom(*a, **k):
        raise llm_router.NoLLMAvailable("no backend configured")

    monkeypatch.setattr(llm_router, "complete", boom)

    assert matcher.score(listings, "resume text", FakeConfig()) == []


def test_score_caps_batch_at_max_listings_per_call(monkeypatch):
    listings = [_listing(f"Job {i}", f"https://a/{i}") for i in range(matcher.MAX_LISTINGS_PER_CALL + 10)]
    captured = {}

    def fake_complete(config, prompt, *, system=None):
        captured["prompt"] = prompt
        return "[]"

    monkeypatch.setattr(llm_router, "complete", fake_complete)

    matcher.score(listings, "resume text", FakeConfig())

    for i in range(matcher.MAX_LISTINGS_PER_CALL):
        assert f"Job {i}" in captured["prompt"]
    assert f"Job {matcher.MAX_LISTINGS_PER_CALL + 5}" not in captured["prompt"]
