"""Convenience git commands with a hard secrets gate. You invoke every step — staging, scanning,
drafting a commit message, pushing — nothing here runs on its own timing. Never force-pushes."""

import subprocess

from doctor_raven.config import Config
from doctor_raven.core import llm_router
from doctor_raven.features.git_ops.models import SecretFinding
from doctor_raven.features.git_ops.secret_scanner import scan_diff, scan_filenames

COMMIT_MESSAGE_SYSTEM_PROMPT = (
    "You are Doctor Raven, drafting a git commit message. Given a `git diff --cached` output, write "
    "a concise conventional-commit-style message: a short imperative summary line (max ~72 chars), "
    "optionally a blank line and 1-3 bullet points for non-obvious detail. No preamble, no quotes "
    "around it, just the message itself. Base it only on what's actually in the diff."
)

MAX_DIFF_PROMPT_CHARS = 8000


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def has_changes() -> bool:
    return bool(_run(["git", "status", "--porcelain"]).stdout.strip())


def stage_all() -> None:
    _run(["git", "add", "-A"])


def staged_files() -> list[str]:
    return [line for line in _run(["git", "diff", "--cached", "--name-only"]).stdout.splitlines() if line]


def scan_staged() -> list[SecretFinding]:
    diff_text = _run(["git", "diff", "--cached"]).stdout
    return scan_diff(diff_text) + scan_filenames(staged_files())


def draft_commit_message(config: Config) -> str:
    diff_text = _run(["git", "diff", "--cached"]).stdout[:MAX_DIFF_PROMPT_CHARS]
    if not diff_text.strip():
        return ""
    try:
        return llm_router.complete(config, diff_text, system=COMMIT_MESSAGE_SYSTEM_PROMPT).strip()
    except llm_router.NoLLMAvailable:
        return ""


def commit(message: str) -> subprocess.CompletedProcess:
    return _run(["git", "commit", "-m", message])


def current_branch() -> str:
    return _run(["git", "branch", "--show-current"]).stdout.strip()


def has_upstream() -> bool:
    return _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]).returncode == 0


def scan_outgoing() -> tuple[list[SecretFinding], str]:
    """Returns (findings, scope_note) — scope_note names what was actually scanned, since a
    first push of a new branch has no upstream to diff against and gets a bounded fallback."""
    if has_upstream():
        diff_text = _run(["git", "diff", "@{u}..HEAD"]).stdout
        changed_files = [line for line in _run(["git", "diff", "--name-only", "@{u}..HEAD"]).stdout.splitlines() if line]
        return scan_diff(diff_text) + scan_filenames(changed_files), "diff against upstream"

    log_text = _run(["git", "log", "-p", "-20"]).stdout
    changed_files = [line for line in _run(["git", "log", "--name-only", "--pretty=format:", "-20"]).stdout.splitlines() if line]
    findings = scan_diff(log_text) + scan_filenames(changed_files)
    return findings, "last 20 commits (no upstream set yet — first push, not full history)"


def push() -> subprocess.CompletedProcess:
    return _run(["git", "push"])


def push_set_upstream(branch: str) -> subprocess.CompletedProcess:
    return _run(["git", "push", "-u", "origin", branch])
