"""Turns a raw factual event into a short desktop-notification line in Doctor Raven's voice,
instead of a raw template string. Falls back to the plain fact if the LLM is unavailable or the
phrasing can't be trusted — a notification must never silently disappear, and a fabricated CVE
ID in a phrased popup is a strictly worse outcome than a dry but accurate one."""

import re

from doctor_raven.config import Config
from doctor_raven.core import llm_router

VOICE_SYSTEM_PROMPT = (
    "You are Doctor Raven, okumuraven's personal AI assistant — warm, a little dry-witted, never "
    "robotic. Rewrite the following factual event as ONE short sentence you'd actually say out loud "
    "as a desktop notification — under 150 characters, no preamble, no quotes around it, just the "
    "line itself. Keep every concrete detail exactly as given (numbers, CVE IDs, filenames, "
    "percentages, names) — never invent, add, or guess at anything not already in the input."
)

MAX_POPUP_LENGTH = 200
CVE_ID_PATTERN = re.compile(r"CVE-\d{4}-\d+", re.IGNORECASE)


def _is_trustworthy(raw_message: str, phrased: str) -> bool:
    original_ids = {m.upper() for m in CVE_ID_PATTERN.findall(raw_message)}
    phrased_ids = {m.upper() for m in CVE_ID_PATTERN.findall(phrased)}
    return phrased_ids <= original_ids


def phrase_for_popup(raw_message: str, config: Config) -> str:
    try:
        phrased = llm_router.complete(config, raw_message, system=VOICE_SYSTEM_PROMPT)
    except llm_router.NoLLMAvailable:
        return raw_message

    phrased = phrased.strip().strip('"')
    if not phrased or len(phrased) > MAX_POPUP_LENGTH or not _is_trustworthy(raw_message, phrased):
        return raw_message
    return phrased
