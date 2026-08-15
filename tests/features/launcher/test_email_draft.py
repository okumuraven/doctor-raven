from doctor_raven.core import llm_router
from doctor_raven.features.launcher import email_draft


class FakeConfig:
    pass


def test_draft_parses_subject_and_body(monkeypatch):
    monkeypatch.setattr(
        llm_router, "complete", lambda *a, **k: "SUBJECT: Meeting tomorrow\nBODY: Let's meet at 10am.\\nSee you then."
    )

    result = email_draft.draft("boss@example.com", "scheduling a meeting", FakeConfig())

    assert result.to == "boss@example.com"
    assert result.subject == "Meeting tomorrow"
    assert result.body == "Let's meet at 10am.\nSee you then."


def test_draft_falls_back_when_model_output_is_malformed(monkeypatch):
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "some unstructured text with no markers")

    result = email_draft.draft("x@example.com", "the original request", FakeConfig())

    assert result.subject == "Regarding your message"
    assert result.body == "the original request"


def test_open_in_mail_client_builds_mailto_link(monkeypatch):
    calls = []
    monkeypatch.setattr(email_draft.webbrowser, "open", lambda url: calls.append(url) or True)

    drafted = email_draft.EmailDraft(to="a@example.com", subject="Hi there", body="Body text")
    assert email_draft.open_in_mail_client(drafted) is True

    assert calls[0].startswith("mailto:a%40example.com?")
    assert "subject=Hi%20there" in calls[0]
    assert "body=Body%20text" in calls[0]
