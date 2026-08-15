"""LLM-driven idea generation and research digests for saved topics, plus a daily synthesis
grounding the LLM in real signal: recent project git activity, trending tech headlines, and
newly actively-exploited CVEs — instead of it inventing generic ideas from nothing."""

import re
from dataclasses import dataclass

from doctor_raven.config import Config
from doctor_raven.core import llm_router
from doctor_raven.features.research import cyber_feed, project_tracker, tech_feed
from doctor_raven.features.research.cyber_feed import KevEntry
from doctor_raven.features.research.models import Topic
from doctor_raven.features.research.project_tracker import ProjectActivity
from doctor_raven.features.research.tech_feed import TechStory

BRAINSTORM_SYSTEM_PROMPT = (
    "You are a terse technical brainstorming partner for a software engineer and cybersecurity "
    "specialist. Given a topic, produce 3-5 concrete, actionable ideas or angles worth investigating "
    "today. No fluff, no preamble, just a tight bullet list."
)

DIGEST_SYSTEM_PROMPT = (
    "You are a terse technical research assistant for a software engineer and cybersecurity specialist. "
    "Given their recent project git activity and a short list of trending tech headlines and newly "
    "actively-exploited CVEs, write a tight 3-5 bullet digest: call out anything directly relevant to "
    "their current project first, then anything else worth 30 seconds of attention today. "
    "Use ONLY the specific projects, headlines, and CVE IDs given to you below — never invent a CVE ID, "
    "project name, or headline that isn't literally present in the lists below. If a list is empty, say "
    "so plainly (e.g. 'no newly exploited CVEs this period') instead of making one up. No fluff."
)

CVE_ID_PATTERN = re.compile(r"CVE-\d{4}-\d+", re.IGNORECASE)


def _flag_unverified_cves(synthesis: str, kev_entries: list[KevEntry]) -> str:
    """Small local models can fabricate plausible-looking CVE IDs during synthesis. Cross-check
    every CVE ID the model actually output against the real fetched KEV data — never trust an
    LLM's word alone for something this consequential — and flag anything that doesn't match."""
    real_ids = {e.cve_id.upper() for e in kev_entries}
    mentioned = {m.upper() for m in CVE_ID_PATTERN.findall(synthesis)}
    fabricated = mentioned - real_ids
    if not fabricated:
        return synthesis
    return (
        synthesis
        + f"\n[WARNING: model referenced {', '.join(sorted(fabricated))}, not present in the fetched "
        "CISA KEV data — likely hallucinated, do not act on it]"
    )


@dataclass(frozen=True)
class DigestResult:
    project_context: list[ProjectActivity]
    tech_stories: list[TechStory]
    kev_entries: list[KevEntry]
    synthesis: str
    topic_brainstorms: dict[str, str]


def _format_projects(projects: list[ProjectActivity]) -> str:
    if not projects:
        return "(no recent git activity detected in the workspace)"
    return "\n".join(f'- {p.name} (branch {p.branch}): "{p.last_commit_message}" at {p.last_commit_at}' for p in projects)


def _format_stories(stories: list[TechStory]) -> str:
    if not stories:
        return "(none fetched)"
    return "\n".join(f"- {s.title} ({s.points} pts)" for s in stories)


def _format_kev(entries: list[KevEntry]) -> str:
    if not entries:
        return "(none added recently)"
    return "\n".join(f"- {e.cve_id}: {e.name} ({e.vendor} {e.product}), added {e.date_added}" for e in entries)


def brainstorm_topic(config: Config, topic: Topic, *, deep: bool = False) -> str:
    prompt = f"Topic: {topic.name}\n"
    if topic.description:
        prompt += f"Context: {topic.description}\n"
    prompt += "Give me today's brainstorm."

    return llm_router.complete(config, prompt, deep=deep, system=BRAINSTORM_SYSTEM_PROMPT)


def brainstorm_all(config: Config, topics: list[Topic], *, deep: bool = False) -> dict[str, str]:
    results: dict[str, str] = {}
    for topic in topics:
        try:
            results[topic.name] = brainstorm_topic(config, topic, deep=deep)
        except llm_router.NoLLMAvailable as exc:
            results[topic.name] = f"[skipped: {exc}]"
    return results


def daily_digest(config: Config, topics: list[Topic], *, deep: bool = False) -> DigestResult:
    projects = project_tracker.list_recent_projects(config.workspace_root, limit=2)

    try:
        stories = tech_feed.fetch_recent_stories(config.lookback_days)
    except tech_feed.TechFeedUnavailable as exc:
        stories = []
        stories_error = str(exc)
    else:
        stories_error = None

    try:
        kev_entries = cyber_feed.fetch_recent_kev(config.lookback_days)
    except cyber_feed.KevFeedUnavailable as exc:
        kev_entries = []
        kev_error = str(exc)
    else:
        kev_error = None

    prompt = (
        f"Recent project activity (most recent first):\n{_format_projects(projects)}\n\n"
        f"Trending tech headlines (last {config.lookback_days}d):\n{_format_stories(stories)}\n\n"
        f"Newly actively-exploited CVEs (last {config.lookback_days}d):\n{_format_kev(kev_entries)}\n\n"
        "Give me today's digest."
    )
    try:
        synthesis = llm_router.complete(config, prompt, deep=deep, system=DIGEST_SYSTEM_PROMPT)
        synthesis = _flag_unverified_cves(synthesis, kev_entries)
    except llm_router.NoLLMAvailable as exc:
        synthesis = f"[skipped: {exc}]"

    if stories_error:
        synthesis += f"\n[tech headlines unavailable: {stories_error}]"
    if kev_error:
        synthesis += f"\n[CVE feed unavailable: {kev_error}]"

    return DigestResult(
        project_context=projects,
        tech_stories=stories,
        kev_entries=kev_entries,
        synthesis=synthesis,
        topic_brainstorms=brainstorm_all(config, topics, deep=deep),
    )
