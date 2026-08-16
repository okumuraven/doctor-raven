import pytest
import requests as real_requests

from doctor_raven.features.notifications import discord_client


class FakeResponse:
    def raise_for_status(self):
        pass


def test_send_message_raises_when_no_webhook_url():
    with pytest.raises(discord_client.DiscordUnavailable):
        discord_client.send_message("", "hi")


def test_send_message_posts_content(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(discord_client.requests, "post", fake_post)
    discord_client.send_message("https://discord.example/webhook", "hello there")

    assert captured["url"] == "https://discord.example/webhook"
    assert captured["json"] == {"content": "hello there"}


def test_send_message_truncates_long_content(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(discord_client.requests, "post", fake_post)
    discord_client.send_message("https://discord.example/webhook", "x" * 3000)

    sent = captured["json"]["content"]
    assert len(sent) == discord_client.DISCORD_CONTENT_LIMIT
    assert sent.endswith("(truncated)")


def test_send_message_raises_on_request_failure(monkeypatch):
    def boom(*a, **k):
        raise real_requests.RequestException("network down")

    monkeypatch.setattr(discord_client.requests, "post", boom)

    with pytest.raises(discord_client.DiscordUnavailable):
        discord_client.send_message("https://discord.example/webhook", "hi")
