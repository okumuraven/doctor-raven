"""Thin client for posting to a Discord channel via an incoming webhook — no bot token, no
gateway connection, just one POST per message."""

import requests

DISCORD_CONTENT_LIMIT = 2000
_TRUNCATION_SUFFIX = "\n…(truncated)"


class DiscordUnavailable(RuntimeError):
    pass


def send_message(webhook_url: str, content: str, timeout: float = 10.0) -> None:
    if not webhook_url:
        raise DiscordUnavailable("No Discord webhook URL configured.")

    if len(content) > DISCORD_CONTENT_LIMIT:
        content = content[: DISCORD_CONTENT_LIMIT - len(_TRUNCATION_SUFFIX)] + _TRUNCATION_SUFFIX

    try:
        resp = requests.post(webhook_url, json={"content": content}, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise DiscordUnavailable(f"Discord webhook request failed: {exc}") from exc
