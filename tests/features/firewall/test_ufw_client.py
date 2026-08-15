import subprocess

from doctor_raven.features.firewall import ufw_client

SAMPLE_STATUS_ACTIVE = """Status: active

     To                         Action      From
     --                         ------      ----
[ 1] 22/tcp                     ALLOW IN    Anywhere
[ 2] 8080/tcp                   ALLOW IN    10.0.0.5
[ 3] 9000/tcp                   DENY IN     Anywhere
"""

SAMPLE_STATUS_INACTIVE = "Status: inactive\n"


def _fake_run(returncode=0, stdout="", stderr=""):
    def _run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)

    return _run


def test_status_parses_active_and_rules(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(stdout=SAMPLE_STATUS_ACTIVE))

    result = ufw_client.status()

    assert result.active is True
    assert len(result.rules) == 3
    assert result.rules[0] == ufw_client.FirewallRule(
        number=1, action="ALLOW", port="22/tcp", direction="in", source="Anywhere"
    )
    assert result.rules[1].source == "10.0.0.5"
    assert result.rules[2].action == "DENY"


def test_status_parses_inactive(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(stdout=SAMPLE_STATUS_INACTIVE))

    result = ufw_client.status()

    assert result.active is False
    assert result.rules == []


def test_status_raises_on_failure(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode=1, stderr="permission denied"))

    try:
        ufw_client.status()
        assert False, "expected UFWUnavailable"
    except ufw_client.UFWUnavailable as exc:
        assert "permission denied" in str(exc)


def test_is_ssh_allowed_true_when_rule_present(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(stdout=SAMPLE_STATUS_ACTIVE))
    assert ufw_client.is_ssh_allowed() is True


def test_is_ssh_allowed_false_when_active_without_ssh_rule(monkeypatch):
    no_ssh = "Status: active\n\n     To    Action  From\n     --    ------  ----\n[ 1] 8080/tcp  ALLOW IN  Anywhere\n"
    monkeypatch.setattr(subprocess, "run", _fake_run(stdout=no_ssh))
    assert ufw_client.is_ssh_allowed() is False


def test_is_ssh_allowed_true_when_inactive(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(stdout=SAMPLE_STATUS_INACTIVE))
    assert ufw_client.is_ssh_allowed() is True


def test_allow_builds_plain_spec_without_source(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ufw_client.allow(8080, "tcp", None)
    assert captured["args"] == ["sudo", "ufw", "allow", "8080/tcp"]


def test_allow_builds_scoped_spec_with_source(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ufw_client.allow(8080, "tcp", "10.0.0.5")
    assert captured["args"] == ["sudo", "ufw", "allow", "from", "10.0.0.5", "to", "any", "port", "8080", "proto", "tcp"]


def test_delete_rule_uses_force(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ufw_client.delete_rule(2)
    assert captured["args"] == ["sudo", "ufw", "--force", "delete", "2"]
