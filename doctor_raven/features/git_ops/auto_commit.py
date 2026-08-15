"""Auto-commit sweep for daemon-enabled projects: fires only once uncommitted changes have
gone idle (nothing touched in the last N minutes — a heuristic for "you've stopped editing for
now"), runs the same secrets gate as the manual commit path, and commits locally with an
AI-drafted message. Never pushes — that always stays your call via `raven git push`."""

import subprocess
import time
from pathlib import Path

from doctor_raven.config import Config
from doctor_raven.features.git_ops import repo_ops


def _changed_paths(project_path: Path) -> list[str]:
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=project_path)
    paths = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        paths.append(line[3:].split(" -> ")[-1])
    return paths


def is_idle(project_path: Path, idle_minutes: float) -> bool:
    paths = _changed_paths(project_path)
    if not paths:
        return False

    now = time.time()
    mtimes = []
    for path in paths:
        try:
            mtimes.append((project_path / path).stat().st_mtime)
        except OSError:
            continue  # deleted or otherwise gone — not a sign of active editing

    if not mtimes:
        return True  # every change was a deletion; nothing left that could still be "in progress"

    return (now - max(mtimes)) >= idle_minutes * 60


def try_auto_commit(project_path: Path, config: Config) -> str | None:
    """Returns a human-readable outcome description, or None if there was nothing to do."""
    if not repo_ops.has_changes(project_path):
        return None

    if repo_ops.is_detached_head(project_path):
        # Nobody's here to decide "save this to a branch or not" — an unattended commit into
        # detached HEAD could quietly become unreachable, so just leave it for you to handle.
        return "held off — repo is in detached HEAD; switch to a branch first, then `raven git commit` yourself"

    repo_ops.stage_all(project_path)
    findings = repo_ops.scan_staged(project_path)
    if findings:
        kinds = ", ".join(sorted({f.kind for f in findings}))
        return f"held off committing — found potential secret(s) ({kinds}); review with `raven git commit`"

    hygiene_findings = repo_ops.scan_staged_hygiene(project_path)

    message = repo_ops.draft_commit_message(config, project_path) or "chore: automatic checkpoint (Doctor Raven)"
    result = repo_ops.commit(message, project_path)
    if result.returncode != 0:
        return f"commit failed: {result.stderr.strip()[:200]}"

    outcome = f"committed: {message.splitlines()[0]}"
    if hygiene_findings:
        # Informational, not blocking — nobody's here to confirm, and a stray build artifact
        # isn't a security risk, just worth a nudge to fix your .gitignore.
        outcome += f" (note: {len(hygiene_findings)} file(s) included that probably shouldn't be tracked — check your .gitignore)"
    return outcome
