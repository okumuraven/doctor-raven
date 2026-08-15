import pytest

from doctor_raven.core import llm_router
from doctor_raven.llm import claude_client, ollama_client


class FakeConfig:
    ollama_host = "http://fake:11434"
    ollama_model = "llama3.2"
    claude_model = "claude-sonnet-5"
    anthropic_api_key = None


def test_complete_deep_happy_path(monkeypatch):
    monkeypatch.setattr(claude_client, "complete", lambda *a, **k: "claude says hi")
    assert llm_router.complete(FakeConfig(), "hi", deep=True) == "claude says hi"


def test_complete_deep_wraps_claude_unavailable_as_no_llm_available(monkeypatch):
    def boom(*a, **k):
        raise claude_client.ClaudeUnavailable("no key set")

    monkeypatch.setattr(claude_client, "complete", boom)

    with pytest.raises(llm_router.NoLLMAvailable):
        llm_router.complete(FakeConfig(), "hi", deep=True)


def test_complete_local_happy_path(monkeypatch):
    monkeypatch.setattr(ollama_client, "complete", lambda *a, **k: "ollama says hi")
    assert llm_router.complete(FakeConfig(), "hi") == "ollama says hi"


def test_complete_raises_when_ollama_down_and_no_key(monkeypatch):
    def boom(*a, **k):
        raise ollama_client.OllamaUnavailable("down")

    monkeypatch.setattr(ollama_client, "complete", boom)

    with pytest.raises(llm_router.NoLLMAvailable):
        llm_router.complete(FakeConfig(), "hi")


def test_complete_falls_back_to_claude_when_ollama_down_and_key_set(monkeypatch):
    config = FakeConfig()
    config.anthropic_api_key = "sk-test"

    def boom(*a, **k):
        raise ollama_client.OllamaUnavailable("down")

    monkeypatch.setattr(ollama_client, "complete", boom)
    monkeypatch.setattr(claude_client, "complete", lambda *a, **k: "claude fallback")

    assert llm_router.complete(config, "hi") == "claude fallback"


def test_complete_wraps_claude_unavailable_in_fallback_path(monkeypatch):
    config = FakeConfig()
    config.anthropic_api_key = "sk-test"

    def ollama_boom(*a, **k):
        raise ollama_client.OllamaUnavailable("down")

    def claude_boom(*a, **k):
        raise claude_client.ClaudeUnavailable("also down")

    monkeypatch.setattr(ollama_client, "complete", ollama_boom)
    monkeypatch.setattr(claude_client, "complete", claude_boom)

    with pytest.raises(llm_router.NoLLMAvailable):
        llm_router.complete(config, "hi")
