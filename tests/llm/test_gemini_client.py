import pytest
import requests as real_requests

from doctor_raven.llm import gemini_client


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _candidate_payload(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_complete_raises_when_no_api_key():
    with pytest.raises(gemini_client.GeminiUnavailable):
        gemini_client.complete(None, "gemini-2.5-flash", "hi")


def test_complete_returns_text_on_success(monkeypatch):
    monkeypatch.setattr(gemini_client.requests, "post", lambda *a, **k: FakeResponse(_candidate_payload("hello there")))
    assert gemini_client.complete("gm-test", "gemini-2.5-flash", "hi") == "hello there"


def test_complete_sends_api_key_and_system_instruction(monkeypatch):
    captured = {}

    def fake_post(url, params=None, json=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["json"] = json
        return FakeResponse(_candidate_payload("ok"))

    monkeypatch.setattr(gemini_client.requests, "post", fake_post)
    gemini_client.complete("gm-test", "gemini-2.5-flash", "hi", system="be terse")

    assert captured["params"] == {"key": "gm-test"}
    assert "gemini-2.5-flash:generateContent" in captured["url"]
    assert captured["json"]["contents"][0]["parts"][0]["text"] == "hi"
    assert captured["json"]["systemInstruction"]["parts"][0]["text"] == "be terse"


def test_complete_raises_on_request_failure(monkeypatch):
    def boom(*a, **k):
        raise real_requests.RequestException("network down")

    monkeypatch.setattr(gemini_client.requests, "post", boom)

    with pytest.raises(gemini_client.GeminiUnavailable):
        gemini_client.complete("gm-test", "gemini-2.5-flash", "hi")


def test_complete_raises_when_no_candidates(monkeypatch):
    monkeypatch.setattr(gemini_client.requests, "post", lambda *a, **k: FakeResponse({"candidates": []}))

    with pytest.raises(gemini_client.GeminiUnavailable):
        gemini_client.complete("gm-test", "gemini-2.5-flash", "hi")


def test_complete_raises_with_block_reason_when_prompt_blocked(monkeypatch):
    payload = {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}}
    monkeypatch.setattr(gemini_client.requests, "post", lambda *a, **k: FakeResponse(payload))

    with pytest.raises(gemini_client.GeminiUnavailable, match="SAFETY"):
        gemini_client.complete("gm-test", "gemini-2.5-flash", "hi")


def test_complete_raises_when_text_is_empty(monkeypatch):
    monkeypatch.setattr(gemini_client.requests, "post", lambda *a, **k: FakeResponse(_candidate_payload("")))

    with pytest.raises(gemini_client.GeminiUnavailable):
        gemini_client.complete("gm-test", "gemini-2.5-flash", "hi")
