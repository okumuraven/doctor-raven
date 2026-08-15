import subprocess
from pathlib import Path

from doctor_raven.features.git_ops import repo_ops


def _init_repo(path: Path) -> None:
    path.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def _commit_something(path: Path, name: str = "app.py") -> None:
    (path / name).write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "commit"], cwd=path, check=True)


def test_is_detached_head_false_on_a_branch(tmp_path):
    _init_repo(tmp_path)
    _commit_something(tmp_path)
    assert repo_ops.is_detached_head(tmp_path) is False


def test_is_detached_head_true_after_checking_out_a_commit(tmp_path):
    _init_repo(tmp_path)
    _commit_something(tmp_path)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "checkout", "-q", sha], cwd=tmp_path, check=True)

    assert repo_ops.is_detached_head(tmp_path) is True


def test_branch_exists_true_for_current_branch(tmp_path):
    _init_repo(tmp_path)
    _commit_something(tmp_path)
    branch = repo_ops.current_branch(tmp_path)
    assert repo_ops.branch_exists(branch, tmp_path) is True


def test_branch_exists_false_for_unknown_name(tmp_path):
    _init_repo(tmp_path)
    _commit_something(tmp_path)
    assert repo_ops.branch_exists("does-not-exist", tmp_path) is False


def test_create_branch_and_switch(tmp_path):
    _init_repo(tmp_path)
    _commit_something(tmp_path)

    result = repo_ops.create_branch("feature-x", tmp_path)

    assert result.returncode == 0
    assert repo_ops.current_branch(tmp_path) == "feature-x"


def test_switch_branch_back_and_forth(tmp_path):
    _init_repo(tmp_path)
    _commit_something(tmp_path)
    original = repo_ops.current_branch(tmp_path)
    repo_ops.create_branch("feature-x", tmp_path)

    result = repo_ops.switch_branch(original, tmp_path)

    assert result.returncode == 0
    assert repo_ops.current_branch(tmp_path) == original


def test_unpushed_commit_count_zero_without_upstream(tmp_path):
    _init_repo(tmp_path)
    _commit_something(tmp_path)
    assert repo_ops.unpushed_commit_count(tmp_path) == 0


def test_unpushed_commit_count_with_upstream(tmp_path):
    origin_path = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin_path)], check=True)

    work_path = tmp_path / "work"
    _init_repo(work_path)
    _commit_something(work_path)
    subprocess.run(["git", "remote", "add", "origin", str(origin_path)], cwd=work_path, check=True)
    repo_ops.push_set_upstream(repo_ops.current_branch(work_path), work_path)

    _commit_something(work_path, "extra.py")
    _commit_something(work_path, "extra2.py")

    assert repo_ops.unpushed_commit_count(work_path) == 2


def test_checkout_remote_tracking_creates_local_branch(tmp_path):
    origin_path = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin_path)], check=True)

    work_path = tmp_path / "work"
    _init_repo(work_path)
    _commit_something(work_path)
    subprocess.run(["git", "remote", "add", "origin", str(origin_path)], cwd=work_path, check=True)
    main_branch = repo_ops.current_branch(work_path)
    repo_ops.push_set_upstream(main_branch, work_path)

    repo_ops.create_branch("teammate-branch", work_path)
    _commit_something(work_path, "teammate.py")
    subprocess.run(["git", "push", "-u", "origin", "teammate-branch"], cwd=work_path, check=True)

    clone_path = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(origin_path), str(clone_path)], check=True)

    result = repo_ops.checkout_remote_tracking("teammate-branch", clone_path)

    assert result.returncode == 0
    assert repo_ops.current_branch(clone_path) == "teammate-branch"


def test_stash_push_and_pop_roundtrip(tmp_path):
    _init_repo(tmp_path)
    _commit_something(tmp_path)
    (tmp_path / "app.py").write_text("changed")

    push_result = repo_ops.stash_push("wip", tmp_path)
    assert push_result.returncode == 0
    assert (tmp_path / "app.py").read_text() == "x"  # working tree restored to last commit
    assert len(repo_ops.stash_list(tmp_path)) == 1

    pop_result = repo_ops.stash_pop(tmp_path)
    assert pop_result.returncode == 0
    assert (tmp_path / "app.py").read_text() == "changed"
    assert repo_ops.stash_list(tmp_path) == []


def test_stash_list_empty_when_nothing_stashed(tmp_path):
    _init_repo(tmp_path)
    _commit_something(tmp_path)
    assert repo_ops.stash_list(tmp_path) == []
