"""Routes completion requests to local Ollama by default, Claude for 'deep' requests or as a fallback."""

from doctor_raven.config import Config
from doctor_raven.llm import claude_client, ollama_client

DEFAULT_PERSONA_PROMPT = (
    "You are Doctor Raven, a terse technical assistant for a principal full-stack engineer, database "
    "architect, and SOC/cybersecurity analyst. Default to a zero-trust security posture: flag OWASP Top 10 "
    "risks (injection, XSS, SSRF, broken auth) unprompted when relevant, prefer parameterized queries and "
    "explicit input validation, and call out insecure defaults instead of silently accepting them. Be "
    "direct and precise — no filler, no disclaimers, no 'as an AI' framing. If a question has a security "
    "angle, address it even if not explicitly asked."
)


class NoLLMAvailable(RuntimeError):
    pass


def complete(config: Config, prompt: str, *, deep: bool = False, system: str | None = None) -> str:
    system = system or DEFAULT_PERSONA_PROMPT

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
