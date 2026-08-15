import subprocess
from pathlib import Path

from doctor_raven.features.research import project_tracker


def _commit(path: Path, message: str, when: str, *, init: bool = False) -> None:
    if init:
        path.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / f"{message.replace(' ', '_')}.txt").write_text(message)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    env = {"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when, "PATH": "/usr/bin:/bin"}
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=path, check=True, env=env)


def _init_repo(path: Path, commit_message: str, when: str = "2026-08-01T00:00:00") -> None:
    _commit(path, commit_message, when, init=True)


def test_ranks_by_most_recent_commit(tmp_path):
    _init_repo(tmp_path / "project-a", "initial a", "2026-08-01T00:00:00")
    _init_repo(tmp_path / "project-b", "initial b", "2026-08-02T00:00:00")
    _commit(tmp_path / "project-a", "second a", "2026-08-03T00:00:00")

    projects = project_tracker.list_recent_projects(str(tmp_path))
    assert projects[0].name == "project-a"
    assert projects[0].last_commit_message == "second a"
    assert projects[1].name == "project-b"


def test_ignores_non_git_directories(tmp_path):
    (tmp_path / "not-a-repo").mkdir()
    assert project_tracker.list_recent_projects(str(tmp_path)) == []


def test_missing_workspace_root_returns_empty(tmp_path):
    assert project_tracker.list_recent_projects(str(tmp_path / "nope")) == []


def test_respects_limit(tmp_path):
    for i in range(3):
        _init_repo(tmp_path / f"proj{i}", f"commit {i}")

    assert len(project_tracker.list_recent_projects(str(tmp_path), limit=2)) == 2
