"""Thin client for a local Ollama server."""

import requests


class OllamaUnavailable(RuntimeError):
    pass


def is_reachable(host: str, timeout: float = 1.5) -> bool:
    try:
        resp = requests.get(f"{host}/api/tags", timeout=timeout)
        return resp.ok
    except requests.RequestException:
        return False


def complete(host: str, model: str, prompt: str, system: str | None = None, timeout: float = 60.0) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system

    try:
        resp = requests.post(f"{host}/api/generate", json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaUnavailable(f"Ollama at {host} is unreachable or errored: {exc}") from exc

    data = resp.json()
    text = data.get("response")
    if not text:
        raise OllamaUnavailable(f"Ollama returned an empty response for model '{model}'")
    return text.strip()
