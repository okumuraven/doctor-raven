from doctor_raven.features.system_health import guard as guard_module
from doctor_raven.features.system_health.guard import diagnose, evaluate
from doctor_raven.features.system_health.models import ProcessUsage, SystemStatus


class FakeConfig:
    temp_warn_c = 75.0
    temp_critical_c = 90.0
    load_warn_per_core = 0.85
    load_critical_per_core = 1.5


def test_evaluate_normal():
    status = SystemStatus(cpu_temp_c=50.0, load_1m=1.0, core_count=8)
    assert evaluate(status, FakeConfig()).level == "normal"


def test_evaluate_hot_on_temp():
    status = SystemStatus(cpu_temp_c=80.0, load_1m=1.0, core_count=8)
    assert evaluate(status, FakeConfig()).level == "hot"


def test_evaluate_hot_on_load():
    status = SystemStatus(cpu_temp_c=50.0, load_1m=7.0, core_count=8)  # 0.875/core
    assert evaluate(status, FakeConfig()).level == "hot"


def test_evaluate_critical_on_temp():
    status = SystemStatus(cpu_temp_c=95.0, load_1m=1.0, core_count=8)
    assert evaluate(status, FakeConfig()).level == "critical"


def test_evaluate_critical_on_load():
    status = SystemStatus(cpu_temp_c=50.0, load_1m=13.0, core_count=8)  # 1.625/core
    assert evaluate(status, FakeConfig()).level == "critical"


def test_evaluate_handles_missing_temp_sensor():
    status = SystemStatus(cpu_temp_c=None, load_1m=1.0, core_count=8)
    assert evaluate(status, FakeConfig()).level == "normal"


def test_diagnose_names_ollama_when_it_is_top_consumer(monkeypatch):
    monkeypatch.setattr(
        guard_module.diagnostics,
        "top_processes",
        lambda limit=5: [ProcessUsage(pid=1, name="ollama", cpu_percent=90.0)],
    )
    result = diagnose(SystemStatus(cpu_temp_c=95.0, load_1m=1.0, core_count=8))
    assert "ollama" in result.recommendation.lower()
    assert "--deep" in result.recommendation


def test_diagnose_names_unrelated_process(monkeypatch):
    monkeypatch.setattr(
        guard_module.diagnostics,
        "top_processes",
        lambda limit=5: [ProcessUsage(pid=42, name="firefox", cpu_percent=75.0)],
    )
    result = diagnose(SystemStatus(cpu_temp_c=95.0, load_1m=1.0, core_count=8))
    assert "firefox" in result.recommendation
    assert "not Doctor Raven" in result.recommendation
