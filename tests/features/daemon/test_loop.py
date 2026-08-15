from doctor_raven.features.daemon import loop as loop_module
from doctor_raven.features.system_health.models import Diagnosis, SystemStatus, ThrottleDecision


class FakeConfig:
    temp_warn_c = 75.0
    temp_critical_c = 90.0
    load_warn_per_core = 0.85
    load_critical_per_core = 1.5


def _patch_health(monkeypatch, level: str, reason: str = "test reason"):
    monkeypatch.setattr(loop_module.system_health, "read_status", lambda: SystemStatus(50.0, 1.0, 8))
    monkeypatch.setattr(loop_module.system_health, "evaluate", lambda status, config: ThrottleDecision(level, reason))
    monkeypatch.setattr(
        loop_module.system_health, "diagnose", lambda status: Diagnosis(top_processes=[], recommendation="do X")
    )


def test_no_notification_on_first_tick_when_already_normal(monkeypatch):
    _patch_health(monkeypatch, "normal")
    calls = []
    monkeypatch.setattr(loop_module.notifications, "notify_and_log", lambda *a, **k: calls.append(a))

    result = loop_module._check_system_health(FakeConfig(), last_level=None)

    assert result == "normal"
    assert calls == []


def test_notifies_on_first_tick_when_already_hot(monkeypatch):
    _patch_health(monkeypatch, "hot")
    calls = []
    monkeypatch.setattr(loop_module.notifications, "notify_and_log", lambda *a, **k: calls.append(a))

    result = loop_module._check_system_health(FakeConfig(), last_level=None)

    assert result == "hot"
    assert len(calls) == 1


def test_no_notification_when_level_unchanged(monkeypatch):
    _patch_health(monkeypatch, "hot")
    calls = []
    monkeypatch.setattr(loop_module.notifications, "notify_and_log", lambda *a, **k: calls.append(a))

    result = loop_module._check_system_health(FakeConfig(), last_level="hot")

    assert result == "hot"
    assert calls == []


def test_notifies_on_recovery_to_normal(monkeypatch):
    _patch_health(monkeypatch, "normal")
    calls = []
    monkeypatch.setattr(loop_module.notifications, "notify_and_log", lambda *a, **k: calls.append(a))

    result = loop_module._check_system_health(FakeConfig(), last_level="critical")

    assert result == "normal"
    assert len(calls) == 1
    assert "back to normal" in calls[0][0]


def test_check_reminders_fires_and_marks_due_reminders(isolated_db, monkeypatch):
    from doctor_raven.features import reminders

    reminders.add_reminder("Fire me", "2020-01-01T00:00")
    reminders.add_reminder("Not yet", "2099-01-01T00:00")

    calls = []
    monkeypatch.setattr(loop_module.notifications, "notify_and_log", lambda *a, **k: calls.append(a))

    loop_module._check_reminders(FakeConfig())

    assert len(calls) == 1
    assert [r.message for r in reminders.list_reminders()] == ["Not yet"]
