"""LLM-driven idea generation and research digests for saved topics."""

from doctor_raven.config import Config
from doctor_raven.core import llm_router
from doctor_raven.features.research.models import Topic

BRAINSTORM_SYSTEM_PROMPT = (
    "You are a terse technical brainstorming partner for a software engineer and cybersecurity "
    "specialist. Given a topic, produce 3-5 concrete, actionable ideas or angles worth investigating "
    "today. No fluff, no preamble, just a tight bullet list."
)


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
