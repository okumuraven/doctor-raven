from doctor_raven.features.notifications import service as service_module


class FakeConfig:
    pass


def test_notify_and_log_always_logs_and_fires_popup_when_dashboard_not_running(monkeypatch, isolated_db):
    monkeypatch.setattr(service_module, "is_dashboard_running", lambda: False)
    monkeypatch.setattr(service_module, "phrase_for_popup", lambda message, config: f"voiced: {message}")
    calls = []
    monkeypatch.setattr(service_module, "notify", lambda title, message: calls.append((title, message)))

    service_module.notify_and_log("Title", "Message", source="test", config=FakeConfig())

    assert calls == [(service_module.POPUP_TITLE, "voiced: Message")]
    from doctor_raven.features.notifications import store

    logged = store.list_recent()
    assert [e.title for e in logged] == ["Title"]
    assert [e.message for e in logged] == ["Message"]  # history stays raw/precise, not voiced


def test_notify_and_log_suppresses_popup_but_still_logs_when_dashboard_running(monkeypatch, isolated_db):
    monkeypatch.setattr(service_module, "is_dashboard_running", lambda: True)
    monkeypatch.setattr(service_module, "phrase_for_popup", lambda message, config: f"voiced: {message}")
    calls = []
    monkeypatch.setattr(service_module, "notify", lambda title, message: calls.append((title, message)))

    service_module.notify_and_log("Title", "Message", source="test", config=FakeConfig())

    assert calls == []
    from doctor_raven.features.notifications import store

    assert [e.title for e in store.list_recent()] == ["Title"]
