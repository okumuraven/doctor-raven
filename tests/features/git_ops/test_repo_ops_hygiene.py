import subprocess
from pathlib import Path

from doctor_raven.features.git_ops import repo_ops


def _init_repo(path: Path) -> None:
    path.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def test_repo_root_returns_toplevel(tmp_path):
    _init_repo(tmp_path)
    nested = tmp_path / "sub" / "dir"
    nested.mkdir(parents=True)

    assert repo_ops.repo_root(nested) == tmp_path.resolve()


def test_repo_root_none_outside_a_repo(tmp_path):
    assert repo_ops.repo_root(tmp_path) is None


def test_scan_staged_hygiene_flags_pycache(tmp_path):
    _init_repo(tmp_path)
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "mod.cpython-313.pyc").write_bytes(b"x")
    repo_ops.stage_all(tmp_path)

    findings = repo_ops.scan_staged_hygiene(tmp_path)

    assert any("__pycache__" in f.file for f in findings)


def test_scan_staged_hygiene_clean_for_normal_files(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("print('hi')")
    repo_ops.stage_all(tmp_path)

    assert repo_ops.scan_staged_hygiene(tmp_path) == []


def test_gitignore_status_missing(tmp_path):
    _init_repo(tmp_path)
    assert repo_ops.gitignore_status(tmp_path) == "No .gitignore found in this repo."


def test_gitignore_status_clean_when_populated(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("__pycache__/\n")
    assert repo_ops.gitignore_status(tmp_path) is None


def test_gitignore_status_none_outside_a_repo(tmp_path):
    assert repo_ops.gitignore_status(tmp_path) is None
