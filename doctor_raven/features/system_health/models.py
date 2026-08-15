"""Data models for CPU thermal/load status, throttle decisions, and cause diagnosis."""

from dataclasses import dataclass
from typing import Literal

ThrottleLevel = Literal["normal", "hot", "critical"]


@dataclass(frozen=True)
class SystemStatus:
    cpu_temp_c: float | None
    load_1m: float
    core_count: int

    @property
    def load_per_core(self) -> float:
        return self.load_1m / self.core_count if self.core_count else self.load_1m


@dataclass(frozen=True)
class ThrottleDecision:
    level: ThrottleLevel
    reason: str


@dataclass(frozen=True)
class ProcessUsage:
    pid: int
    name: str
    cpu_percent: float


@dataclass(frozen=True)
class Diagnosis:
    top_processes: list[ProcessUsage]
    recommendation: str
