"""apt-based update checking and (explicitly gated) application."""

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class UpgradeStatus:
    upgradable_count: int
    packages: list[str]


def refresh_index() -> tuple[bool, str]:
    """Runs `sudo apt-get update`. Read-refresh only, does not change installed packages."""
    result = subprocess.run(
        ["sudo", "apt-get", "update"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def list_upgradable() -> UpgradeStatus:
    result = subprocess.run(
        ["apt", "list", "--upgradable"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    lines = [
        line for line in result.stdout.splitlines() if line and not line.startswith("Listing...")
    ]
    packages = [line.split("/")[0] for line in lines]
    return UpgradeStatus(upgradable_count=len(packages), packages=packages)


def apply_upgrades() -> tuple[bool, str]:
    """Runs `sudo apt-get -y upgrade`. Caller is responsible for getting explicit user confirmation first."""
    result = subprocess.run(
        ["sudo", "apt-get", "-y", "upgrade"],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    return result.returncode == 0, (result.stdout + result.stderr).strip()
