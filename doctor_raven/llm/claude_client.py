"""Thin client for the Anthropic Claude API, used for 'deep' reasoning requests."""

import anthropic


class ClaudeUnavailable(RuntimeError):
    pass


def complete(api_key: str | None, model: str, prompt: str, system: str | None = None, max_tokens: int = 1024) -> str:
    if not api_key:
        raise ClaudeUnavailable(
            "ANTHROPIC_API_KEY is not set in the environment. "
            "Export it (e.g. in your shell profile or a systemd EnvironmentFile) to enable deep/Claude requests."
        )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system or "You are a concise, technically precise assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as exc:
        raise ClaudeUnavailable(f"Claude API request failed: {exc}") from exc

    parts = [block.text for block in response.content if block.type == "text"]
    text = "".join(parts).strip()
    if not text:
        raise ClaudeUnavailable("Claude API returned an empty response")
    return text
