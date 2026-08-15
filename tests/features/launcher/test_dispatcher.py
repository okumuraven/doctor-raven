import pytest

from doctor_raven.core import llm_router
from doctor_raven.features.launcher import dispatcher, skills


class FakeConfig:
    terminal_command = ""
    search_engine_url = "https://duckduckgo.com/?q="


def test_interpret_parses_clean_json(monkeypatch):
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: '{"skill": "web_search", "params": {"query": "rust"}}')

    result = dispatcher.interpret("search for rust", FakeConfig())

    assert result == {"skill": "web_search", "params": {"query": "rust"}}


def test_interpret_strips_markdown_fences(monkeypatch):
    monkeypatch.setattr(
        llm_router, "complete", lambda *a, **k: '```json\n{"skill": "open_browser", "params": {"url": "x.com"}}\n```'
    )

    result = dispatcher.interpret("open x.com", FakeConfig())

    assert result == {"skill": "open_browser", "params": {"url": "x.com"}}


def test_interpret_returns_none_for_unrecognized_skill(monkeypatch):
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: '{"skill": "delete_everything"}')
    assert dispatcher.interpret("do something dangerous", FakeConfig()) is None


def test_interpret_returns_none_for_explicit_unknown(monkeypatch):
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: '{"skill": "unknown"}')
    assert dispatcher.interpret("asdkjfh nonsense", FakeConfig()) is None


def test_interpret_returns_none_on_malformed_json(monkeypatch):
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "not json at all")
    assert dispatcher.interpret("whatever", FakeConfig()) is None


def test_interpret_returns_none_when_llm_unavailable(monkeypatch):
    def boom(*a, **k):
        raise llm_router.NoLLMAvailable("no model")

    monkeypatch.setattr(llm_router, "complete", boom)
    assert dispatcher.interpret("whatever", FakeConfig()) is None


def test_dispatch_open_browser(monkeypatch):
    monkeypatch.setattr(skills.webbrowser, "open", lambda url: True)
    result = dispatcher.dispatch("open_browser", {"url": "example.com"}, FakeConfig())
    assert result.email_draft is None
    assert "example.com" in result.message


def test_dispatch_web_search_requires_query():
    with pytest.raises(skills.SkillError):
        dispatcher.dispatch("web_search", {}, FakeConfig())


def test_dispatch_open_browser_requires_url():
    with pytest.raises(skills.SkillError):
        dispatcher.dispatch("open_browser", {}, FakeConfig())


def test_dispatch_draft_email_requires_to_and_about():
    with pytest.raises(skills.SkillError):
        dispatcher.dispatch("draft_email", {"to": "a@example.com"}, FakeConfig())


def test_dispatch_draft_email_returns_email_draft_result(monkeypatch):
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "SUBJECT: Hi\nBODY: Body text")

    result = dispatcher.dispatch("draft_email", {"to": "a@example.com", "about": "saying hi"}, FakeConfig())

    assert result.email_draft is not None
    assert result.email_draft.to == "a@example.com"
    assert result.email_draft.subject == "Hi"


def test_dispatch_unknown_skill_raises():
    with pytest.raises(skills.SkillError):
        dispatcher.dispatch("not_a_real_skill", {}, FakeConfig())
