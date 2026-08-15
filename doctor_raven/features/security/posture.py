"""Read-only local security posture checks. Never elevates privileges silently —
if a check needs root it reports 'insufficient privileges' instead of invoking sudo,
since a silent sudo call would either hang on a password prompt or bypass consent."""

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class PostureCheck:
    name: str
    ok: bool | None  # True = healthy, False = attention needed, None = inconclusive
    summary: str


def _run(cmd: list[str], timeout: float = 15.0) -> tuple[int, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, (result.stdout + result.stderr)


def listening_ports() -> PostureCheck:
    if not shutil.which("ss"):
        return PostureCheck("listening_ports", None, "'ss' not found, cannot enumerate listening sockets")

    code, output = _run(["ss", "-tulpn"])
    if code != 0:
        return PostureCheck("listening_ports", None, "ss failed to run")

    lines = [line for line in output.splitlines()[1:] if line.strip()]
    return PostureCheck("listening_ports", True, f"{len(lines)} listening socket(s) — run `ss -tulpn` for detail")


def firewall_status() -> PostureCheck:
    if shutil.which("ufw"):
        code, output = _run(["ufw", "status"])
        if "permission denied" in output.lower() or code != 0:
            return PostureCheck("firewall", None, "ufw present but needs root to read status")
        if "Status: active" in output:
            return PostureCheck("firewall", True, "ufw active")
        return PostureCheck("firewall", False, "ufw installed but inactive")

    return PostureCheck("firewall", None, "ufw not installed — no firewall status available without root iptables access")


def failed_logins(since: str = "today") -> PostureCheck:
    if not shutil.which("journalctl"):
        return PostureCheck("failed_logins", None, "journalctl not found")

    code, output = _run(["journalctl", "-q", "--since", since, "--no-pager"], timeout=20.0)
    if code != 0 and not output.strip():
        return PostureCheck("failed_logins", None, "insufficient privileges to read the journal")

    failed_count = sum(1 for line in output.splitlines() if "Failed password" in line or "authentication failure" in line)
    ok = failed_count == 0
    summary = "no failed auth attempts" if ok else f"{failed_count} failed auth attempt(s) since {since}"
    return PostureCheck("failed_logins", ok, summary)


def recent_logins(count: int = 5) -> PostureCheck:
    if not shutil.which("last"):
        return PostureCheck("recent_logins", None, "'last' not found")

    code, output = _run(["last", "-n", str(count)])
    if code != 0:
        return PostureCheck("recent_logins", None, "last failed to run")

    lines = [line for line in output.splitlines() if line.strip() and not line.startswith("wtmp begins")]
    return PostureCheck("recent_logins", True, f"last {len(lines)} login(s) available — run `last` for detail")


def run_all() -> list[PostureCheck]:
    return [listening_ports(), firewall_status(), failed_logins(), recent_logins()]
