from pathlib import Path

from doctor_raven.features.git_ops import registry


def test_disabled_by_default(isolated_db):
    assert registry.is_enabled(Path("/some/project")) is False


def test_enable_then_is_enabled(isolated_db):
    project = Path("/some/project")
    registry.enable(project)
    assert registry.is_enabled(project) is True


def test_enable_is_idempotent(isolated_db):
    project = Path("/some/project")
    registry.enable(project)
    registry.enable(project)  # must not raise (UNIQUE constraint)
    assert registry.list_enabled() == [str(project)]


def test_disable_removes_and_reports_true(isolated_db):
    project = Path("/some/project")
    registry.enable(project)
    assert registry.disable(project) is True
    assert registry.is_enabled(project) is False


def test_disable_reports_false_when_not_enabled(isolated_db):
    assert registry.disable(Path("/never/enabled")) is False


def test_list_enabled_returns_all_sorted(isolated_db):
    registry.enable(Path("/b/project"))
    registry.enable(Path("/a/project"))
    assert registry.list_enabled() == ["/a/project", "/b/project"]
