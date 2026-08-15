"""Thin subprocess wrapper around the `ufw` binary. Every call is built from a list of literal
arguments — never a shell string — so this cannot be coerced into running anything beyond an
exact `sudo ufw <args>` invocation. All ufw operations need root, including reading status, so
every call goes through sudo; the caller (cli.py) has already gotten explicit confirmation
before any mutating function here is invoked."""

import re
import subprocess

from doctor_raven.features.firewall.models import FirewallRule, FirewallStatus

_RULE_LINE = re.compile(r"^\[\s*(\d+)\]\s+(.*)$")


class UFWUnavailable(RuntimeError):
    pass


def _run(args: list[str], timeout: float = 15.0) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["sudo", "ufw", *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise UFWUnavailable("ufw is not installed. Run `raven doctor` to install it.") from exc


def _parse_rule_line(line: str) -> FirewallRule | None:
    match = _RULE_LINE.match(line)
    if not match:
        return None

    fields = re.split(r"\s{2,}", match.group(2).strip())
    if len(fields) < 3:
        return None

    port, action_field, source = fields[0], fields[1], fields[2]
    direction = "out" if "OUT" in action_field else "in"
    for word in ("ALLOW", "DENY", "REJECT", "LIMIT"):
        if word in action_field:
            action = word
            break
    else:
        action = action_field

    return FirewallRule(number=int(match.group(1)), action=action, port=port, direction=direction, source=source)


def status() -> FirewallStatus:
    result = _run(["status", "numbered"])
    if result.returncode != 0:
        raise UFWUnavailable((result.stderr or result.stdout or "ufw status failed").strip())

    output = result.stdout
    rules = [rule for line in output.splitlines() if (rule := _parse_rule_line(line)) is not None]
    return FirewallStatus(active="Status: active" in output, rules=rules)


def is_ssh_allowed() -> bool:
    """True if port 22 has an inbound ALLOW rule, or ufw is inactive (nothing is being
    enforced yet, so there is nothing to be locked out of)."""
    current = status()
    if not current.active:
        return True
    return any(rule.action == "ALLOW" and rule.direction == "in" and rule.port.startswith("22/") for rule in current.rules)


def _scoped_args(verb: str, port: int, proto: str, source: str | None) -> list[str]:
    if source:
        return [verb, "from", source, "to", "any", "port", str(port), "proto", proto]
    return [verb, f"{port}/{proto}"]


def allow(port: int, proto: str, source: str | None) -> subprocess.CompletedProcess:
    return _run(_scoped_args("allow", port, proto, source))


def deny(port: int, proto: str, source: str | None) -> subprocess.CompletedProcess:
    return _run(_scoped_args("deny", port, proto, source))


def delete_rule(rule_number: int) -> subprocess.CompletedProcess:
    return _run(["--force", "delete", str(rule_number)])


def enable() -> subprocess.CompletedProcess:
    return _run(["--force", "enable"])


def disable() -> subprocess.CompletedProcess:
    return _run(["disable"])
