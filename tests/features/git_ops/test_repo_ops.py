import subprocess
from pathlib import Path

from doctor_raven.core import llm_router
from doctor_raven.features.git_ops import repo_ops


class FakeConfig:
    pass


def _init_repo(path: Path) -> None:
    path.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def test_has_changes_false_on_clean_repo(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert repo_ops.has_changes() is False


def test_has_changes_true_with_untracked_file(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "new.txt").write_text("hi")
    monkeypatch.chdir(tmp_path)
    assert repo_ops.has_changes() is True


def test_stage_all_and_staged_files(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    monkeypatch.chdir(tmp_path)

    repo_ops.stage_all()
    assert set(repo_ops.staged_files()) == {"a.txt", "b.txt"}


def test_scan_staged_flags_sensitive_filename(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / ".env").write_text("SECRET=x")
    monkeypatch.chdir(tmp_path)

    repo_ops.stage_all()
    assert any(f.file == ".env" for f in repo_ops.scan_staged())


def test_scan_staged_flags_secret_content(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "config.py").write_text('api_key = "sk-1234567890abcdef"\n')
    monkeypatch.chdir(tmp_path)

    repo_ops.stage_all()
    assert any(f.kind == "generic secret assignment" for f in repo_ops.scan_staged())


def test_scan_staged_clean_when_nothing_suspicious(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n")
    monkeypatch.chdir(tmp_path)

    repo_ops.stage_all()
    assert repo_ops.scan_staged() == []


def test_commit_creates_a_real_commit(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("print('hi')\n")
    monkeypatch.chdir(tmp_path)
    repo_ops.stage_all()

    result = repo_ops.commit("test: initial commit")
    assert result.returncode == 0

    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True)
    assert "test: initial commit" in log.stdout


def test_current_branch_returns_nonempty(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    repo_ops.stage_all()
    repo_ops.commit("init")

    assert repo_ops.current_branch()


def test_has_upstream_false_without_remote(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    repo_ops.stage_all()
    repo_ops.commit("init")

    assert repo_ops.has_upstream() is False


def test_scan_outgoing_without_upstream_scans_recent_log(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "config.py").write_text('api_key = "sk-1234567890abcdef"\n')
    monkeypatch.chdir(tmp_path)
    repo_ops.stage_all()
    repo_ops.commit("add secret oops")

    findings, scope_note = repo_ops.scan_outgoing()
    assert "no upstream" in scope_note
    assert any(f.kind == "generic secret assignment" for f in findings)


def test_scan_outgoing_without_upstream_also_catches_sensitive_filenames(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / ".env").write_text("just some plain text, no obvious secret pattern")
    monkeypatch.chdir(tmp_path)
    repo_ops.stage_all()
    repo_ops.commit("oops committed .env")

    findings, _ = repo_ops.scan_outgoing()
    assert any(f.file == ".env" for f in findings)


def test_scan_outgoing_with_upstream_also_catches_sensitive_filenames(tmp_path, monkeypatch):
    origin_path = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin_path)], check=True)

    work_path = tmp_path / "work"
    _init_repo(work_path)
    (work_path / "app.py").write_text("x")
    subprocess.run(["git", "remote", "add", "origin", str(origin_path)], cwd=work_path, check=True)
    monkeypatch.chdir(work_path)
    repo_ops.stage_all()
    repo_ops.commit("init")
    repo_ops.push_set_upstream(repo_ops.current_branch())

    (work_path / ".env").write_text("just some plain text, no obvious secret pattern")
    repo_ops.stage_all()
    repo_ops.commit("oops committed .env")

    findings, scope_note = repo_ops.scan_outgoing()
    assert scope_note == "diff against upstream"
    assert any(f.file == ".env" for f in findings)


def test_push_set_upstream_and_has_upstream_after(tmp_path, monkeypatch):
    origin_path = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin_path)], check=True)

    work_path = tmp_path / "work"
    _init_repo(work_path)
    (work_path / "app.py").write_text("x")
    subprocess.run(["git", "remote", "add", "origin", str(origin_path)], cwd=work_path, check=True)
    monkeypatch.chdir(work_path)
    repo_ops.stage_all()
    repo_ops.commit("init")

    assert repo_ops.has_upstream() is False
    result = repo_ops.push_set_upstream(repo_ops.current_branch())

    assert result.returncode == 0
    assert repo_ops.has_upstream() is True


def test_draft_commit_message_empty_when_nothing_staged(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert repo_ops.draft_commit_message(FakeConfig()) == ""


def test_draft_commit_message_falls_back_when_llm_unavailable(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    repo_ops.stage_all()

    def boom(*a, **k):
        raise llm_router.NoLLMAvailable("no model")

    monkeypatch.setattr(repo_ops.llm_router, "complete", boom)
    assert repo_ops.draft_commit_message(FakeConfig()) == ""


def test_draft_commit_message_uses_llm_output(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    repo_ops.stage_all()

    monkeypatch.setattr(repo_ops.llm_router, "complete", lambda *a, **k: "feat: add app.py")
    assert repo_ops.draft_commit_message(FakeConfig()) == "feat: add app.py"
