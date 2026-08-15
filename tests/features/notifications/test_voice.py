from doctor_raven.core import llm_router
from doctor_raven.features.notifications import voice as voice_module


class FakeConfig:
    pass


def test_uses_phrased_text_when_trustworthy(monkeypatch):
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "Hey, that's the fact, said with a smile.")
    result = voice_module.phrase_for_popup("The fact.", FakeConfig())
    assert result == "Hey, that's the fact, said with a smile."


def test_falls_back_to_raw_message_when_llm_unavailable(monkeypatch):
    def boom(*a, **k):
        raise llm_router.NoLLMAvailable("no model")

    monkeypatch.setattr(llm_router, "complete", boom)
    result = voice_module.phrase_for_popup("The raw fact.", FakeConfig())
    assert result == "The raw fact."


def test_falls_back_when_phrasing_invents_a_cve_not_in_the_original(monkeypatch):
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "Watch out for CVE-2026-9999!")
    result = voice_module.phrase_for_popup("New vuln found in requests.", FakeConfig())
    assert result == "New vuln found in requests."


def test_keeps_phrasing_when_it_repeats_a_real_cve_from_the_original(monkeypatch):
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "Heads up — CVE-2026-1111 just showed up.")
    result = voice_module.phrase_for_popup("New CVE found: CVE-2026-1111 in requests.", FakeConfig())
    assert result == "Heads up — CVE-2026-1111 just showed up."


def test_falls_back_when_phrasing_is_empty(monkeypatch):
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "   ")
    result = voice_module.phrase_for_popup("The raw fact.", FakeConfig())
    assert result == "The raw fact."


def test_falls_back_when_phrasing_is_too_long(monkeypatch):
    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "x" * 300)
    result = voice_module.phrase_for_popup("The raw fact.", FakeConfig())
    assert result == "The raw fact."
