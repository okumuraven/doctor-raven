"""Thin client for the Google Gemini API — Doctor Raven's default completion backend (faster
and more creative than the local Ollama model for everyday requests, at the cost of the
request leaving the machine)."""

import requests

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiUnavailable(RuntimeError):
    pass


def complete(api_key: str | None, model: str, prompt: str, system: str | None = None, timeout: float = 30.0) -> str:
    if not api_key:
        raise GeminiUnavailable(
            "GEMINI_API_KEY is not set in the environment. "
            "Export it, or use --local (Ollama) / --deep (Claude) instead."
        )

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}

    url = f"{GEMINI_API_BASE}/{model}:generateContent"
    try:
        resp = requests.post(url, params={"key": api_key}, json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise GeminiUnavailable(f"Gemini API request failed: {exc}") from exc

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        block_reason = (data.get("promptFeedback") or {}).get("blockReason")
        detail = f" (blocked: {block_reason})" if block_reason else ""
        raise GeminiUnavailable(f"Gemini API returned no candidates{detail}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise GeminiUnavailable("Gemini API returned an empty response")
    return text
