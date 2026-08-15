"""Routes completion requests to local Ollama by default, Claude for 'deep' requests or as a fallback."""

from doctor_raven.config import Config
from doctor_raven.llm import claude_client, ollama_client


class NoLLMAvailable(RuntimeError):
    pass


def complete(config: Config, prompt: str, *, deep: bool = False, system: str | None = None) -> str:
    if deep:
        return claude_client.complete(config.anthropic_api_key, config.claude_model, prompt, system=system)

    try:
        return ollama_client.complete(config.ollama_host, config.ollama_model, prompt, system=system)
    except ollama_client.OllamaUnavailable as ollama_exc:
        if not config.anthropic_api_key:
            raise NoLLMAvailable(
                f"Local Ollama is unavailable ({ollama_exc}) and no ANTHROPIC_API_KEY is set as a fallback. "
                "Run `raven doctor` to check/install Ollama, or export ANTHROPIC_API_KEY."
            ) from ollama_exc
        return claude_client.complete(config.anthropic_api_key, config.claude_model, prompt, system=system)
