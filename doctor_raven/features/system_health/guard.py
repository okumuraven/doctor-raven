"""Compares live CPU status against configured thresholds and, when tripped, diagnoses the cause."""

from doctor_raven.config import Config
from doctor_raven.features.system_health import diagnostics, sensors
from doctor_raven.features.system_health.models import Diagnosis, SystemStatus, ThrottleDecision


def read_status() -> SystemStatus:
    return SystemStatus(
        cpu_temp_c=sensors.read_cpu_temp_c(),
        load_1m=sensors.read_load_1m(),
        core_count=sensors.cpu_count(),
    )


def evaluate(status: SystemStatus, config: Config) -> ThrottleDecision:
    temp = status.cpu_temp_c
    load_per_core = status.load_per_core

    temp_critical = temp is not None and temp >= config.temp_critical_c
    load_critical = load_per_core >= config.load_critical_per_core
    if temp_critical or load_critical:
        reason = f"CPU temp {temp:.0f}°C" if temp_critical else f"load {load_per_core:.2f}/core"
        return ThrottleDecision("critical", f"{reason} at or above the critical threshold")

    temp_hot = temp is not None and temp >= config.temp_warn_c
    load_hot = load_per_core >= config.load_warn_per_core
    if temp_hot or load_hot:
        reason = f"CPU temp {temp:.0f}°C" if temp_hot else f"load {load_per_core:.2f}/core"
        return ThrottleDecision("hot", f"{reason} at or above the warn threshold")

    return ThrottleDecision("normal", "within normal range")


def diagnose(status: SystemStatus | None = None) -> Diagnosis:
    status = status or read_status()
    processes = diagnostics.top_processes()
    return Diagnosis(top_processes=processes, recommendation=diagnostics.build_recommendation(processes))
