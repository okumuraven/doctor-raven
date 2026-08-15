from doctor_raven.features.notifications import service as service_module


def test_notify_and_log_always_logs_and_fires_popup_when_dashboard_not_running(monkeypatch, isolated_db):
    monkeypatch.setattr(service_module, "is_dashboard_running", lambda: False)
    calls = []
    monkeypatch.setattr(service_module, "notify", lambda title, message: calls.append((title, message)))

    service_module.notify_and_log("Title", "Message", source="test")

    assert calls == [("Title", "Message")]
    from doctor_raven.features.notifications import store

    assert [e.title for e in store.list_recent()] == ["Title"]


def test_notify_and_log_suppresses_popup_but_still_logs_when_dashboard_running(monkeypatch, isolated_db):
    monkeypatch.setattr(service_module, "is_dashboard_running", lambda: True)
    calls = []
    monkeypatch.setattr(service_module, "notify", lambda title, message: calls.append((title, message)))

    service_module.notify_and_log("Title", "Message", source="test")

    assert calls == []
    from doctor_raven.features.notifications import store

    assert [e.title for e in store.list_recent()] == ["Title"]
