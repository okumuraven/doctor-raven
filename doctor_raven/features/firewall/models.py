"""Data models for the firewall feature."""

from dataclasses import dataclass
from typing import Callable

import subprocess


@dataclass(frozen=True)
class FirewallRule:
    number: int
    action: str  # "ALLOW", "DENY", "REJECT", or "LIMIT"
    port: str  # e.g. "22/tcp" or "8080/tcp (v6)"
    direction: str  # "in" or "out"
    source: str  # "Anywhere" or a specific IP/CIDR


@dataclass(frozen=True)
class FirewallStatus:
    active: bool
    rules: list[FirewallRule]


@dataclass(frozen=True)
class PreviewedChange:
    """A ufw mutation that hasn't run yet. `description` explains exactly what will happen;
    `warning`, when set, flags a risk (e.g. possible SSH lockout) that the caller must make the
    user acknowledge explicitly before invoking `apply`."""

    description: str
    warning: str | None
    apply: Callable[[], subprocess.CompletedProcess]
