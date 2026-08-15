import subprocess

import pytest

from doctor_raven.features.firewall import service, ufw_client


def test_preview_allow_rejects_bad_port():
    with pytest.raises(service.InvalidRule):
        service.preview_allow(70000, "tcp", None)


def test_preview_allow_rejects_bad_proto():
    with pytest.raises(service.InvalidRule):
        service.preview_allow(8080, "icmp", None)


def test_preview_allow_rejects_bad_source():
    with pytest.raises(service.InvalidRule):
        service.preview_allow(8080, "tcp", "not-an-ip")


def test_preview_allow_has_no_warning():
    change = service.preview_allow(8080, "tcp", None)
    assert change.warning is None
    assert "sudo ufw allow 8080/tcp" in change.description


def test_preview_allow_describes_scoped_source():
    change = service.preview_allow(8080, "tcp", "10.0.0.5")
    assert "from 10.0.0.5" in change.description


def test_preview_deny_warns_on_ssh_port():
    change = service.preview_deny(22, "tcp", None)
    assert change.warning is not None
    assert "SSH" in change.warning


def test_preview_deny_no_warning_on_other_port():
    change = service.preview_deny(8080, "tcp", None)
    assert change.warning is None


def test_preview_delete_describes_rule_number():
    change = service.preview_delete(3)
    assert "delete 3" in change.description
    assert change.warning is None


def test_preview_enable_warns_when_ssh_not_allowed(monkeypatch):
    monkeypatch.setattr(ufw_client, "is_ssh_allowed", lambda: False)
    change = service.preview_enable()
    assert change.warning is not None
    assert "SSH" in change.warning


def test_preview_enable_no_warning_when_ssh_allowed(monkeypatch):
    monkeypatch.setattr(ufw_client, "is_ssh_allowed", lambda: True)
    change = service.preview_enable()
    assert change.warning is None


def test_preview_disable_always_warns():
    change = service.preview_disable()
    assert change.warning is not None


def test_apply_calls_through_to_ufw_client(monkeypatch):
    captured = {}

    def fake_allow(port, proto, source):
        captured["called"] = (port, proto, source)
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(ufw_client, "allow", fake_allow)
    change = service.preview_allow(8080, "tcp", None)
    change.apply()
    assert captured["called"] == (8080, "tcp", None)
