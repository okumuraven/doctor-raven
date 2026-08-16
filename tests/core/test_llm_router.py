import pytest

from doctor_raven.core import llm_router
from doctor_raven.llm import claude_client, gemini_client, ollama_client


class FakeConfig:
    ollama_host = "http://fake:11434"
    ollama_model = "llama3.2"
    claude_model = "claude-sonnet-5"
    gemini_model = "gemini-2.5-flash"
    anthropic_api_key = None
    gemini_api_keys = ["gm-test"]


@pytest.fixture(autouse=True)
def _isolated_rotation_state(tmp_path, monkeypatch):
    """The rotation offset is persisted to a small file under the data dir (so it survives
    across separate short-lived CLI invocations) — redirect it to a throwaway path per test."""
    monkeypatch.setattr(llm_router, "ensure_data_dir", lambda: tmp_path)


def test_complete_deep_happy_path(monkeypatch):
    monkeypatch.setattr(claude_client, "complete", lambda *a, **k: "claude says hi")
    assert llm_router.complete(FakeConfig(), "hi", deep=True) == "claude says hi"


def test_complete_deep_wraps_claude_unavailable_as_no_llm_available(monkeypatch):
    def boom(*a, **k):
        raise claude_client.ClaudeUnavailable("no key set")

    monkeypatch.setattr(claude_client, "complete", boom)

    with pytest.raises(llm_router.NoLLMAvailable):
        llm_router.complete(FakeConfig(), "hi", deep=True)


def test_complete_deep_ignores_local_flag_precedence(monkeypatch):
    """deep takes priority even if local is somehow also set."""
    monkeypatch.setattr(claude_client, "complete", lambda *a, **k: "claude wins")
    assert llm_router.complete(FakeConfig(), "hi", deep=True, local=True) == "claude wins"


def test_complete_default_uses_gemini(monkeypatch):
    monkeypatch.setattr(gemini_client, "complete", lambda *a, **k: "gemini says hi")
    assert llm_router.complete(FakeConfig(), "hi") == "gemini says hi"


def test_complete_default_falls_back_to_ollama_when_gemini_unavailable(monkeypatch):
    def boom(*a, **k):
        raise gemini_client.GeminiUnavailable("no key")

    monkeypatch.setattr(gemini_client, "complete", boom)
    monkeypatch.setattr(ollama_client, "complete", lambda *a, **k: "ollama fallback")

    assert llm_router.complete(FakeConfig(), "hi") == "ollama fallback"


def test_complete_default_falls_back_to_claude_when_gemini_and_ollama_both_down(monkeypatch):
    config = FakeConfig()
    config.anthropic_api_key = "sk-test"

    def gemini_boom(*a, **k):
        raise gemini_client.GeminiUnavailable("no key")

    def ollama_boom(*a, **k):
        raise ollama_client.OllamaUnavailable("down")

    monkeypatch.setattr(gemini_client, "complete", gemini_boom)
    monkeypatch.setattr(ollama_client, "complete", ollama_boom)
    monkeypatch.setattr(claude_client, "complete", lambda *a, **k: "claude last resort")

    assert llm_router.complete(config, "hi") == "claude last resort"


def test_complete_default_raises_when_everything_is_down(monkeypatch):
    def gemini_boom(*a, **k):
        raise gemini_client.GeminiUnavailable("no key")

    def ollama_boom(*a, **k):
        raise ollama_client.OllamaUnavailable("down")

    monkeypatch.setattr(gemini_client, "complete", gemini_boom)
    monkeypatch.setattr(ollama_client, "complete", ollama_boom)

    with pytest.raises(llm_router.NoLLMAvailable):
        llm_router.complete(FakeConfig(), "hi")


def test_complete_raises_gemini_unavailable_message_when_no_keys_configured(monkeypatch):
    config = FakeConfig()
    config.gemini_api_keys = []

    monkeypatch.setattr(ollama_client, "complete", lambda *a, **k: "ollama fallback")
    assert llm_router.complete(config, "hi") == "ollama fallback"


def test_rotation_fails_over_to_second_key_within_one_call(monkeypatch):
    config = FakeConfig()
    config.gemini_api_keys = ["key-a", "key-b", "key-c"]

    def flaky(api_key, *a, **k):
        if api_key == "key-a":
            raise gemini_client.GeminiUnavailable("rate limited")
        return f"success via {api_key}"

    monkeypatch.setattr(gemini_client, "complete", flaky)
    assert llm_router.complete(config, "hi") == "success via key-b"


def test_rotation_only_falls_through_to_ollama_when_all_keys_fail(monkeypatch):
    config = FakeConfig()
    config.gemini_api_keys = ["key-a", "key-b"]

    def all_fail(api_key, *a, **k):
        raise gemini_client.GeminiUnavailable(f"{api_key} down")

    monkeypatch.setattr(gemini_client, "complete", all_fail)
    monkeypatch.setattr(ollama_client, "complete", lambda *a, **k: "ollama fallback")
    assert llm_router.complete(config, "hi") == "ollama fallback"


def test_rotation_advances_starting_key_across_calls(monkeypatch):
    """Round-robin: call 1 starts at key-a, call 2 starts at key-b, etc. — spreads load across
    keys/projects instead of always hitting the same one first."""
    config = FakeConfig()
    config.gemini_api_keys = ["key-a", "key-b", "key-c"]

    attempted_first_key = []

    def record_first_attempt(api_key, *a, **k):
        attempted_first_key.append(api_key)
        return f"ok via {api_key}"

    monkeypatch.setattr(gemini_client, "complete", record_first_attempt)

    llm_router.complete(config, "hi")
    llm_router.complete(config, "hi")
    llm_router.complete(config, "hi")
    llm_router.complete(config, "hi")

    assert attempted_first_key == ["key-a", "key-b", "key-c", "key-a"]


def test_rotation_offset_survives_a_fresh_call_as_if_a_new_process(monkeypatch, tmp_path):
    """The whole point of persisting to disk instead of an in-memory counter: a brand new
    call (standing in for a brand new `raven ask` process) must still see the advanced offset."""
    config = FakeConfig()
    config.gemini_api_keys = ["key-a", "key-b"]
    monkeypatch.setattr(gemini_client, "complete", lambda api_key, *a, **k: api_key)

    first = llm_router.complete(config, "hi")
    assert (tmp_path / llm_router._ROTATION_STATE_FILENAME).read_text().strip() == "1"

    second = llm_router.complete(config, "hi")
    assert (first, second) == ("key-a", "key-b")


def test_rotation_offset_defaults_to_zero_when_state_file_is_corrupt(monkeypatch, tmp_path):
    (tmp_path / llm_router._ROTATION_STATE_FILENAME).write_text("not-a-number")
    config = FakeConfig()
    config.gemini_api_keys = ["key-a", "key-b"]
    monkeypatch.setattr(gemini_client, "complete", lambda api_key, *a, **k: api_key)

    assert llm_router.complete(config, "hi") == "key-a"


def test_complete_local_happy_path(monkeypatch):
    monkeypatch.setattr(ollama_client, "complete", lambda *a, **k: "ollama says hi")
    assert llm_router.complete(FakeConfig(), "hi", local=True) == "ollama says hi"


def test_complete_local_never_touches_gemini(monkeypatch):
    def gemini_boom(*a, **k):
        raise AssertionError("local=True must not call Gemini")

    monkeypatch.setattr(gemini_client, "complete", gemini_boom)
    monkeypatch.setattr(ollama_client, "complete", lambda *a, **k: "ollama says hi")
    assert llm_router.complete(FakeConfig(), "hi", local=True) == "ollama says hi"


def test_complete_local_raises_when_ollama_down_and_no_key(monkeypatch):
    def boom(*a, **k):
        raise ollama_client.OllamaUnavailable("down")

    monkeypatch.setattr(ollama_client, "complete", boom)

    with pytest.raises(llm_router.NoLLMAvailable):
        llm_router.complete(FakeConfig(), "hi", local=True)


def test_complete_local_falls_back_to_claude_when_ollama_down_and_key_set(monkeypatch):
    config = FakeConfig()
    config.anthropic_api_key = "sk-test"

    def boom(*a, **k):
        raise ollama_client.OllamaUnavailable("down")

    monkeypatch.setattr(ollama_client, "complete", boom)
    monkeypatch.setattr(claude_client, "complete", lambda *a, **k: "claude fallback")

    assert llm_router.complete(config, "hi", local=True) == "claude fallback"


def test_complete_local_wraps_claude_unavailable_in_fallback_path(monkeypatch):
    config = FakeConfig()
    config.anthropic_api_key = "sk-test"

    def ollama_boom(*a, **k):
        raise ollama_client.OllamaUnavailable("down")

    def claude_boom(*a, **k):
        raise claude_client.ClaudeUnavailable("also down")

    monkeypatch.setattr(ollama_client, "complete", ollama_boom)
    monkeypatch.setattr(claude_client, "complete", claude_boom)

    with pytest.raises(llm_router.NoLLMAvailable):
        llm_router.complete(config, "hi", local=True)
