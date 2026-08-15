"""Interactive dependency check-and-install. Never installs anything without an explicit per-item confirmation."""

import shutil
import subprocess
from dataclasses import dataclass

from doctor_raven.config import Config
from doctor_raven.llm.ollama_client import is_reachable

APT_PACKAGES = {
    "rkhunter": "rkhunter",
    "lynis": "lynis",
    "clamscan": "clamav",
    "freshclam": "clamav-freshclam",
    "notify-send": "libnotify-bin",
}

OLLAMA_INSTALL_SCRIPT_URL = "https://ollama.com/install.sh"


@dataclass(frozen=True)
class DepStatus:
    name: str
    installed: bool
    detail: str


def check_all(config: Config) -> list[DepStatus]:
    statuses = []

    ollama_binary = shutil.which("ollama") is not None
    ollama_up = is_reachable(config.ollama_host)
    if ollama_binary and ollama_up:
        statuses.append(DepStatus("ollama", True, f"reachable at {config.ollama_host}"))
    elif ollama_binary:
        statuses.append(DepStatus("ollama", False, "binary found but server not responding"))
    else:
        statuses.append(DepStatus("ollama", False, "not installed"))

    for binary in APT_PACKAGES:
        found = shutil.which(binary) is not None
        statuses.append(DepStatus(binary, found, "found" if found else "not installed"))

    return statuses


def _confirm(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in ("y", "yes")


def install_apt_package(binary: str) -> bool:
    package = APT_PACKAGES[binary]
    if not _confirm(f"Install '{package}' via apt (provides `{binary}`)?"):
        print(f"Skipped {package}.")
        return False

    result = subprocess.run(["sudo", "apt-get", "install", "-y", package], timeout=300)
    return result.returncode == 0


def install_ollama() -> bool:
    print(
        "Ollama is not installed. The official install method is running Ollama's install script "
        f"({OLLAMA_INSTALL_SCRIPT_URL}) via `sh`, which downloads and runs its own binary + systemd service.\n"
        "Inspect it yourself first if you want: curl -fsSL " + OLLAMA_INSTALL_SCRIPT_URL
    )
    if not _confirm("Proceed with the official Ollama install script now?"):
        print("Skipped Ollama install.")
        return False

    curl = subprocess.run(["curl", "-fsSL", OLLAMA_INSTALL_SCRIPT_URL], capture_output=True, text=True, timeout=30)
    if curl.returncode != 0:
        print("Failed to download the Ollama install script.")
        return False

    result = subprocess.run(["sh"], input=curl.stdout, text=True, timeout=300)
    return result.returncode == 0


def run_doctor(config: Config) -> None:
    statuses = check_all(config)
    print("Doctor Raven dependency check:")
    for status in statuses:
        marker = "OK " if status.installed else "MISSING"
        print(f"  [{marker}] {status.name}: {status.detail}")

    missing = [s for s in statuses if not s.installed]
    if not missing:
        print("\nAll dependencies present.")
        return

    print()
    for status in missing:
        if status.name == "ollama":
            install_ollama()
        else:
            install_apt_package(status.name)
