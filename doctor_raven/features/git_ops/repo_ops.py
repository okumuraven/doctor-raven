"""Convenience git commands with a hard secrets gate. You invoke every step — staging, scanning,
drafting a commit message, pushing — nothing here runs on its own timing. Never force-pushes.

Every function takes an optional `cwd` so the daemon's auto-commit sweep (features/git_ops/
auto_commit.py) can operate on multiple projects in turn without a process-wide os.chdir(),
which would race with other daemon work (e.g. the background dependency-scan thread) running
in the same process. The interactive `raven git commit`/`push` CLI commands omit it, relying
on the shell's actual working directory, exactly as plain `git` would."""

import subprocess
from pathlib import Path

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


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, cwd=cwd)


def has_changes(cwd: Path | None = None) -> bool:
    return bool(_run(["git", "status", "--porcelain"], cwd).stdout.strip())


def stage_all(cwd: Path | None = None) -> None:
    _run(["git", "add", "-A"], cwd)


def staged_files(cwd: Path | None = None) -> list[str]:
    return [line for line in _run(["git", "diff", "--cached", "--name-only"], cwd).stdout.splitlines() if line]


def scan_staged(cwd: Path | None = None) -> list[SecretFinding]:
    diff_text = _run(["git", "diff", "--cached"], cwd).stdout
    return scan_diff(diff_text) + scan_filenames(staged_files(cwd))


def draft_commit_message(config: Config, cwd: Path | None = None) -> str:
    diff_text = _run(["git", "diff", "--cached"], cwd).stdout[:MAX_DIFF_PROMPT_CHARS]
    if not diff_text.strip():
        return ""
    try:
        return llm_router.complete(config, diff_text, system=COMMIT_MESSAGE_SYSTEM_PROMPT).strip()
    except llm_router.NoLLMAvailable:
        return ""


def commit(message: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return _run(["git", "commit", "-m", message], cwd)


def current_branch(cwd: Path | None = None) -> str:
    return _run(["git", "branch", "--show-current"], cwd).stdout.strip()


def has_upstream(cwd: Path | None = None) -> bool:
    return _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd).returncode == 0


def scan_outgoing(cwd: Path | None = None) -> tuple[list[SecretFinding], str]:
    """Returns (findings, scope_note) — scope_note names what was actually scanned, since a
    first push of a new branch has no upstream to diff against and gets a bounded fallback."""
    if has_upstream(cwd):
        diff_text = _run(["git", "diff", "@{u}..HEAD"], cwd).stdout
        changed_files = [line for line in _run(["git", "diff", "--name-only", "@{u}..HEAD"], cwd).stdout.splitlines() if line]
        return scan_diff(diff_text) + scan_filenames(changed_files), "diff against upstream"

    log_text = _run(["git", "log", "-p", "-20"], cwd).stdout
    changed_files = [line for line in _run(["git", "log", "--name-only", "--pretty=format:", "-20"], cwd).stdout.splitlines() if line]
    findings = scan_diff(log_text) + scan_filenames(changed_files)
    return findings, "last 20 commits (no upstream set yet — first push, not full history)"


def push(cwd: Path | None = None) -> subprocess.CompletedProcess:
    return _run(["git", "push"], cwd)


def push_set_upstream(branch: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return _run(["git", "push", "-u", "origin", branch], cwd)


def is_detached_head(cwd: Path | None = None) -> bool:
    return _run(["git", "symbolic-ref", "-q", "HEAD"], cwd).returncode != 0


def unpushed_commit_count(cwd: Path | None = None) -> int:
    if not has_upstream(cwd):
        return 0
    try:
        return int(_run(["git", "rev-list", "--count", "@{u}..HEAD"], cwd).stdout.strip())
    except ValueError:
        return 0


def branch_exists(name: str, cwd: Path | None = None) -> bool:
    return _run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], cwd).returncode == 0


def create_branch(name: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return _run(["git", "checkout", "-b", name], cwd)


def switch_branch(branch: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return _run(["git", "checkout", branch], cwd)


def checkout_remote_tracking(branch: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Fallback for `raven git switch <branch>` when no local branch of that name exists yet —
    covers the common case of switching to a branch a teammate pushed that you haven't fetched
    a local copy of before."""
    return _run(["git", "checkout", "--track", f"origin/{branch}"], cwd)


def stash_push(message: str | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    args = ["git", "stash", "push"]
    if message:
        args += ["-m", message]
    return _run(args, cwd)


def stash_pop(cwd: Path | None = None) -> subprocess.CompletedProcess:
    return _run(["git", "stash", "pop"], cwd)


def stash_list(cwd: Path | None = None) -> list[str]:
    return [line for line in _run(["git", "stash", "list"], cwd).stdout.splitlines() if line]
