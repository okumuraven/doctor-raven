"""Scores job listings against the stored resume via the LLM — the actual filter that turns a
noisy raw feed into real matches. Proven necessary live: a raw RemoteOK/Remotive keyword pull
returned mostly unrelated roles (a "Facilities Planner", an "Affiliate" listing) alongside the
genuine fits, so keyword matching alone isn't enough — the model has to judge actual fit."""

import json
import re

from doctor_raven.config import Config
from doctor_raven.core import llm_router
from doctor_raven.features.jobs.models import JobListing, JobMatch

MATCH_SYSTEM_PROMPT = (
    "You are Doctor Raven, screening job listings against okumuraven's resume. Given the resume "
    "and a numbered list of job listings (title, company, location, short description), return "
    "ONLY a JSON array of the indices (0-based) that are a genuine, strong fit for their actual "
    'background — not a loose keyword match. For each match include a one-sentence reason. Format: '
    '[{"index": 0, "reason": "..."}]. If none are a real fit, return []. No other text, no markdown fences.'
)

MAX_LISTINGS_PER_CALL = 25
MAX_RESUME_CHARS = 4000


def _format_listings(listings: list[JobListing]) -> str:
    return "\n".join(
        f"{i}. {listing.title} @ {listing.company} ({listing.location}) — {listing.description[:200]}"
        for i, listing in enumerate(listings)
    )


def score(listings: list[JobListing], resume_text: str, config: Config) -> list[JobMatch]:
    if not listings:
        return []

    batch = listings[:MAX_LISTINGS_PER_CALL]
    prompt = f"RESUME:\n{resume_text[:MAX_RESUME_CHARS]}\n\nLISTINGS:\n{_format_listings(batch)}"

    try:
        raw = llm_router.complete(config, prompt, system=MATCH_SYSTEM_PROMPT)
    except llm_router.NoLLMAvailable:
        return []

    cleaned = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []

    matches = []
    for item in parsed:
        if isinstance(item, dict):
            index, reason = item.get("index"), str(item.get("reason", ""))
        elif isinstance(item, int):
            # Smaller local models don't reliably follow the {"index", "reason"} shape and
            # sometimes emit a bare list of indices — still a genuine match, just unlabeled.
            index, reason = item, ""
        else:
            continue
        if not isinstance(index, int) or not (0 <= index < len(batch)):
            continue
        matches.append(JobMatch(listing=batch[index], reason=reason))
    return matches
