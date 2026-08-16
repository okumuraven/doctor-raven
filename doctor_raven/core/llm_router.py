"""Routes completion requests: Gemini by default (fast, creative, cloud) — rotating across every
configured GEMINI_API_KEYS entry so one rate-limited/revoked key doesn't stall a request as
long as another is good — local Ollama when `local=True` is requested (e.g. `--local`, or a
caller that must never leave the machine unattended — see git_ops.repo_ops.draft_commit_message
and notifications.voice.phrase_for_popup), Claude when `deep=True` is requested. If every Gemini
key fails or Ollama errors, falls through to Ollama-then-Claude, so callers only ever need to
handle NoLLMAvailable regardless of path taken."""

from doctor_raven.config import Config, ensure_data_dir
from doctor_raven.llm import claude_client, gemini_client, ollama_client

DEFAULT_PERSONA_PROMPT = (
    "You are Doctor Raven — okumuraven's personal AI assistant: part secretary, part SOC analyst, and "
    "part old friend who happens to know a dangerous amount about security. Talk like a trusted coworker "
    "who's been in the trenches with them, not a manual — warm, a little dry-witted, occasionally "
    "opinionated, never robotic or clinical. Use their name naturally when it fits, the way a real "
    "assistant would, but don't force it into every line. You still default to a zero-trust security "
    "posture — flag OWASP Top 10 risks (injection, XSS, SSRF, broken auth) unprompted when relevant, "
    "prefer parameterized queries and explicit validation, and call out insecure defaults instead of "
    "nodding along — but say it like you actually care about their code, not like a linter. Keep it "
    "tight: personality doesn't mean rambling. No 'as an AI' framing, no corporate hedging, no "
    "disclaimers. If something has a security angle, mention it even if not asked — that's the job, "
    "but ONLY for code/config actually shown to you in this conversation, never otherwise.\n\n"
    "CRITICAL, overrides everything above: you have NOT reviewed okumuraven's code, files, or systems "
    "unless their actual content is pasted into this prompt. You have no filesystem access, no repo "
    "access, nothing. If asked something like 'how does my setup/code look?' with nothing pasted in, "
    "you MUST say plainly that you don't have visibility into their actual code from here and point "
    "them at a real command that would check it (raven sec scan-deps <file>, raven sec posture, raven "
    "sec cve). Do NOT invent example filenames (login.php, config.py, etc.), example libraries, or "
    "example vulnerabilities dressed up as if you found them — even as illustrative examples. Naming a "
    "specific-sounding fake finding is the one failure mode worse than a boring answer.\n\n"
    "This honesty rule is NOT a mode-switch — don't drop into a flat, listy FAQ-bot voice just because "
    "the truthful answer is 'I can't see that from here.' Saying so is still Doctor Raven talking, same "
    "warmth and personality as everywhere else — the constraint is on WHAT you claim to know, not on "
    "HOW you sound saying it."
)


class NoLLMAvailable(RuntimeError):
    pass


_ROTATION_STATE_FILENAME = "gemini_rotation_offset"


def _read_rotation_offset() -> int:
    try:
        return int((ensure_data_dir() / _ROTATION_STATE_FILENAME).read_text().strip())
    except (OSError, ValueError):
        return 0


def _write_rotation_offset(value: int) -> None:
    try:
        (ensure_data_dir() / _ROTATION_STATE_FILENAME).write_text(str(value))
    except OSError:
        pass  # best-effort — rotation still works within this call either way


def _complete_gemini_with_rotation(config: Config, prompt: str, system: str) -> str:
    """Rotates the starting key on every call (round-robin), persisted to a tiny state file
    rather than kept in memory — nearly every invocation of this CLI is its own short-lived
    process, so an in-memory counter would reset to the same first key every single time and
    never actually spread load. Within a single call, if the chosen key fails for any reason,
    the remaining keys are tried in turn before giving up — so one rate-limited or revoked key
    never stalls a request as long as another is still good."""
    keys = config.gemini_api_keys
    if not keys:
        raise gemini_client.GeminiUnavailable(
            "No Gemini API key configured. Set GEMINI_API_KEY (one key) or GEMINI_API_KEYS "
            "(comma-separated, rotates across all of them) in the environment."
        )

    offset = _read_rotation_offset() % len(keys)
    _write_rotation_offset(offset + 1)
    ordered_keys = keys[offset:] + keys[:offset]

    last_exc: gemini_client.GeminiUnavailable | None = None
    for api_key in ordered_keys:
        try:
            return gemini_client.complete(api_key, config.gemini_model, prompt, system=system)
        except gemini_client.GeminiUnavailable as exc:
            last_exc = exc
    raise last_exc


def _complete_local_then_claude(config: Config, prompt: str, system: str) -> str:
    try:
        return ollama_client.complete(config.ollama_host, config.ollama_model, prompt, system=system)
    except ollama_client.OllamaUnavailable as ollama_exc:
        if not config.anthropic_api_key:
            raise NoLLMAvailable(
                f"Local Ollama is unavailable ({ollama_exc}) and no ANTHROPIC_API_KEY is set as a fallback. "
                "Run `raven doctor` to check/install Ollama, or export ANTHROPIC_API_KEY."
            ) from ollama_exc
        try:
            return claude_client.complete(config.anthropic_api_key, config.claude_model, prompt, system=system)
        except claude_client.ClaudeUnavailable as claude_exc:
            raise NoLLMAvailable(str(claude_exc)) from claude_exc


def complete(config: Config, prompt: str, *, deep: bool = False, local: bool = False, system: str | None = None) -> str:
    """Raises NoLLMAvailable on any failure — deep, default, or local — so callers only ever
    need to handle one exception type regardless of which path was taken."""
    system = system or DEFAULT_PERSONA_PROMPT

    if deep:
        try:
            return claude_client.complete(config.anthropic_api_key, config.claude_model, prompt, system=system)
        except claude_client.ClaudeUnavailable as exc:
            raise NoLLMAvailable(str(exc)) from exc

    if local:
        return _complete_local_then_claude(config, prompt, system)

    try:
        return _complete_gemini_with_rotation(config, prompt, system)
    except gemini_client.GeminiUnavailable:
        return _complete_local_then_claude(config, prompt, system)
