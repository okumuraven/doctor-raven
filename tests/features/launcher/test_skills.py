import pytest

from doctor_raven.features.launcher import skills


class FakeConfig:
    search_engine_url = "https://duckduckgo.com/?q="


def test_open_vscode_raises_when_code_not_on_path(monkeypatch):
    monkeypatch.setattr(skills.shutil, "which", lambda name: None)
    with pytest.raises(skills.SkillError, match="PATH"):
        skills.open_vscode(".")


def test_open_vscode_raises_when_path_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(skills.shutil, "which", lambda name: "/usr/bin/code")
    with pytest.raises(skills.SkillError, match="does not exist"):
        skills.open_vscode(str(tmp_path / "nope"))


def test_open_vscode_launches_with_resolved_path(monkeypatch, tmp_path):
    monkeypatch.setattr(skills.shutil, "which", lambda name: "/usr/bin/code")
    calls = []
    monkeypatch.setattr(skills.subprocess, "Popen", lambda args, **kwargs: calls.append(args))

    result = skills.open_vscode(str(tmp_path))

    assert calls == [["code", str(tmp_path)]]
    assert str(tmp_path) in result


def test_open_terminal_uses_configured_command_first(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(skills.subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)))

    skills.open_terminal(str(tmp_path), terminal_command="my-term")

    assert calls[0][0] == ["my-term"]
    assert calls[0][1]["cwd"] == tmp_path


def test_open_terminal_falls_back_when_no_terminal_found(monkeypatch, tmp_path):
    monkeypatch.setattr(skills.shutil, "which", lambda name: None)
    with pytest.raises(skills.SkillError, match="No terminal emulator"):
        skills.open_terminal(str(tmp_path), terminal_command="")


def test_open_browser_adds_scheme_when_missing(monkeypatch):
    calls = []
    monkeypatch.setattr(skills.webbrowser, "open", lambda url: calls.append(url) or True)

    skills.open_browser("example.com")

    assert calls == ["https://example.com"]


def test_open_browser_keeps_existing_scheme(monkeypatch):
    calls = []
    monkeypatch.setattr(skills.webbrowser, "open", lambda url: calls.append(url) or True)

    skills.open_browser("http://example.com")

    assert calls == ["http://example.com"]


def test_open_browser_raises_when_nothing_can_open_it(monkeypatch):
    monkeypatch.setattr(skills.webbrowser, "open", lambda url: False)
    with pytest.raises(skills.SkillError):
        skills.open_browser("https://example.com")


def test_web_search_builds_url_from_configured_engine(monkeypatch):
    calls = []
    monkeypatch.setattr(skills.webbrowser, "open", lambda url: calls.append(url) or True)

    skills.web_search("python asyncio patterns", FakeConfig())

    assert calls == ["https://duckduckgo.com/?q=python%20asyncio%20patterns"]
