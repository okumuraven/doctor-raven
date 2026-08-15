import os
import subprocess
import time
from pathlib import Path

from doctor_raven.core import llm_router
from doctor_raven.features.git_ops import auto_commit


class FakeConfig:
    pass


def _init_repo(path: Path) -> None:
    path.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def test_is_idle_false_with_no_changes(tmp_path):
    _init_repo(tmp_path)
    assert auto_commit.is_idle(tmp_path, idle_minutes=10) is False


def test_is_idle_false_when_recently_touched(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("x")
    assert auto_commit.is_idle(tmp_path, idle_minutes=10) is False


def test_is_idle_true_once_old_enough(tmp_path):
    _init_repo(tmp_path)
    f = tmp_path / "app.py"
    f.write_text("x")
    old_time = time.time() - 700  # ~11.6 minutes ago
    os.utime(f, (old_time, old_time))
    assert auto_commit.is_idle(tmp_path, idle_minutes=10) is True


def test_is_idle_true_when_only_change_is_a_deletion(tmp_path):
    _init_repo(tmp_path)
    f = tmp_path / "app.py"
    f.write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    f.unlink()
    assert auto_commit.is_idle(tmp_path, idle_minutes=10) is True


def test_try_auto_commit_returns_none_when_nothing_changed(tmp_path):
    _init_repo(tmp_path)
    assert auto_commit.try_auto_commit(tmp_path, FakeConfig()) is None


def test_try_auto_commit_holds_off_in_detached_head(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "checkout", "-q", sha], cwd=tmp_path, check=True)

    (tmp_path / "app.py").write_text("changed")

    outcome = auto_commit.try_auto_commit(tmp_path, FakeConfig())

    assert outcome is not None and "detached HEAD" in outcome
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True)
    assert len(log.stdout.strip().splitlines()) == 1  # nothing new committed


def test_try_auto_commit_holds_off_on_secrets(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "settings.py").write_text('api_key = "sk-1234567890abcdef"\n')

    outcome = auto_commit.try_auto_commit(tmp_path, FakeConfig())

    assert outcome is not None and "held off" in outcome
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True)
    assert log.stdout.strip() == ""  # nothing committed


def test_try_auto_commit_commits_clean_changes_with_llm_message(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("print('hi')\n")

    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "feat: add app.py")

    outcome = auto_commit.try_auto_commit(tmp_path, FakeConfig())

    assert outcome == "committed: feat: add app.py"
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True)
    assert "feat: add app.py" in log.stdout


def test_try_auto_commit_notes_hygiene_issues_without_blocking(tmp_path, monkeypatch):
    """Hygiene findings (build artifacts) are informational only in the unattended path — no
    one's there to confirm, and it's not a security risk, just worth a nudge in the message."""
    _init_repo(tmp_path)
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "mod.cpython-313.pyc").write_bytes(b"x")

    monkeypatch.setattr(llm_router, "complete", lambda *a, **k: "chore: wip")

    outcome = auto_commit.try_auto_commit(tmp_path, FakeConfig())

    assert outcome is not None and outcome.startswith("committed: chore: wip")
    assert "probably shouldn't be tracked" in outcome
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True)
    assert "chore: wip" in log.stdout  # committed anyway, not blocked


def test_try_auto_commit_falls_back_to_generic_message_when_llm_unavailable(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("print('hi')\n")

    def boom(*a, **k):
        raise llm_router.NoLLMAvailable("no model")

    monkeypatch.setattr(llm_router, "complete", boom)

    outcome = auto_commit.try_auto_commit(tmp_path, FakeConfig())
    assert outcome is not None and "chore: automatic checkpoint" in outcome
