from doctor_raven.features.notifications import discord_client, service as service_module


class FakeConfig:
    discord_webhook_url = None


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


def test_notify_and_log_posts_to_discord_even_when_dashboard_running(monkeypatch, isolated_db):
    """Discord posting must NOT be suppressed by the dashboard-open check — that suppression
    is about avoiding a redundant *local* popup, which doesn't apply to a remote channel."""
    monkeypatch.setattr(service_module, "is_dashboard_running", lambda: True)
    monkeypatch.setattr(service_module, "phrase_for_popup", lambda message, config: message)
    monkeypatch.setattr(service_module, "notify", lambda *a, **k: None)

    config = FakeConfig()
    config.discord_webhook_url = "https://discord.example/webhook"
    captured = {}
    monkeypatch.setattr(
        discord_client, "send_message", lambda url, content, **k: captured.update(url=url, content=content)
    )

    service_module.notify_and_log("Title", "Message", source="test", config=config)

    assert captured == {"url": "https://discord.example/webhook", "content": "**Title**\nMessage"}


def test_send_discord_noop_when_not_configured(monkeypatch):
    called = []
    monkeypatch.setattr(discord_client, "send_message", lambda *a, **k: called.append(True))
    service_module.send_discord(FakeConfig(), "hi")
    assert called == []


def test_send_discord_swallows_failure(monkeypatch):
    def boom(*a, **k):
        raise discord_client.DiscordUnavailable("webhook rejected")

    monkeypatch.setattr(discord_client, "send_message", boom)
    config = FakeConfig()
    config.discord_webhook_url = "https://discord.example/webhook"

    service_module.send_discord(config, "hi")  # must not raise
