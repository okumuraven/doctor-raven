"""Detects recently active projects by scanning a workspace root for git repositories.
Read-only (`git log`/`git branch`) — never fetches, pulls, or touches repo state."""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectActivity:
    name: str
    path: Path
    last_commit_at: str  # ISO 8601, from `git log --format=%aI`
    last_commit_message: str
    branch: str


def _git_repos(workspace_root: Path) -> list[Path]:
    if not workspace_root.exists():
        return []
    return [child for child in workspace_root.iterdir() if child.is_dir() and (child / ".git").exists()]


def _last_commit(repo: Path) -> ProjectActivity | None:
    try:
        log = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%aI\x1f%s"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        branch = subprocess.run(
            ["git", "-C", str(repo), "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None

    if log.returncode != 0 or not log.stdout.strip():
        return None

    when, _, message = log.stdout.strip().partition("\x1f")
    return ProjectActivity(
        name=repo.name,
        path=repo,
        last_commit_at=when,
        last_commit_message=message,
        branch=branch.stdout.strip() or "unknown",
    )


def list_recent_projects(workspace_root: str, limit: int = 5) -> list[ProjectActivity]:
    root = Path(workspace_root).expanduser()
    activities = [a for a in (_last_commit(repo) for repo in _git_repos(root)) if a is not None]
    activities.sort(key=lambda a: a.last_commit_at, reverse=True)
    return activities[:limit]
