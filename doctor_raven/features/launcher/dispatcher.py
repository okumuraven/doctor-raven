"""Natural-language entry point: classifies a free-text request into ONE of a fixed, small set
of known skills — never a freeform decision — and extracts simple parameters, then dispatches.
If the request doesn't confidently match a known skill, it says so rather than guessing."""

import json
import re
from dataclasses import dataclass

from doctor_raven.config import Config
from doctor_raven.core import llm_router
from doctor_raven.features.launcher import email_draft, skills
from doctor_raven.features.launcher.email_draft import EmailDraft

KNOWN_SKILLS = ("open_vscode", "open_terminal", "open_browser", "web_search", "draft_email")

DISPATCH_SYSTEM_PROMPT = (
    "You classify a user's request into exactly one of these skills, or 'unknown' if none "
    "confidently match:\n"
    '- open_vscode: params {"path": <folder, optional>}\n'
    '- open_terminal: params {"path": <folder, optional>}\n'
    '- open_browser: params {"url": <url>}\n'
    '- web_search: params {"query": <search text>}\n'
    '- draft_email: params {"to": <recipient>, "about": <what it\'s about>}\n'
    'Respond with ONLY a JSON object: {"skill": "<name>", "params": {...}}. No other text, no '
    'markdown fences, no explanation. If nothing matches confidently, {"skill": "unknown"}.'
)


@dataclass(frozen=True)
class DispatchResult:
    message: str
    email_draft: EmailDraft | None = None


def interpret(request: str, config: Config) -> dict | None:
    """Returns {"skill": ..., "params": {...}} or None if it couldn't confidently classify."""
    try:
        raw = llm_router.complete(config, request, system=DISPATCH_SYSTEM_PROMPT)
    except llm_router.NoLLMAvailable:
        return None

    cleaned = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or parsed.get("skill") not in KNOWN_SKILLS:
        return None
    return {"skill": parsed["skill"], "params": parsed.get("params") or {}}


def dispatch(skill: str, params: dict, config: Config) -> DispatchResult:
    if skill == "open_vscode":
        return DispatchResult(message=skills.open_vscode(params.get("path")))
    if skill == "open_terminal":
        return DispatchResult(message=skills.open_terminal(params.get("path"), config.terminal_command))
    if skill == "open_browser":
        url = params.get("url")
        if not url:
            raise skills.SkillError("No URL given.")
        return DispatchResult(message=skills.open_browser(url))
    if skill == "web_search":
        query = params.get("query")
        if not query:
            raise skills.SkillError("No search query given.")
        return DispatchResult(message=skills.web_search(query, config))
    if skill == "draft_email":
        to, about = params.get("to"), params.get("about")
        if not to or not about:
            raise skills.SkillError("Need both a recipient and what it's about.")
        drafted = email_draft.draft(to, about, config)
        return DispatchResult(message="Drafted an email for your review.", email_draft=drafted)
    raise skills.SkillError(f"Unknown skill: {skill}")
