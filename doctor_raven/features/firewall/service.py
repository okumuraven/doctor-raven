"""Validates rule inputs and builds a PreviewedChange for every mutation — cli.py always shows
the preview and gets confirmation before calling `.apply()`. Nothing in this module ever runs
a ufw command directly."""

import ipaddress

from doctor_raven.features.firewall import ufw_client
from doctor_raven.features.firewall.models import PreviewedChange

VALID_PROTOCOLS = ("tcp", "udp")
SSH_PORT = 22


class InvalidRule(ValueError):
    pass


def _validate_port(port: int) -> None:
    if not (1 <= port <= 65535):
        raise InvalidRule(f"Port must be between 1 and 65535, got {port}")


def _validate_proto(proto: str) -> str:
    proto = proto.lower()
    if proto not in VALID_PROTOCOLS:
        raise InvalidRule(f"Protocol must be one of {VALID_PROTOCOLS}, got '{proto}'")
    return proto


def _validate_source(source: str | None) -> str | None:
    if source is None:
        return None
    try:
        ipaddress.ip_network(source, strict=False)
    except ValueError as exc:
        raise InvalidRule(f"'{source}' is not a valid IP address or CIDR range") from exc
    return source


def _describe(verb: str, effect: str, port: int, proto: str, source: str | None) -> str:
    if source:
        command = f"sudo ufw {verb} from {source} to any port {port} proto {proto}"
    else:
        command = f"sudo ufw {verb} {port}/{proto}"
    scope = f" from {source}" if source else ""
    return f"This will run: {command}\nEffect: connections to port {port}/{proto}{scope} will be {effect}."


def preview_allow(port: int, proto: str, source: str | None) -> PreviewedChange:
    _validate_port(port)
    proto = _validate_proto(proto)
    source = _validate_source(source)
    return PreviewedChange(
        description=_describe("allow", "allowed through", port, proto, source),
        warning=None,
        apply=lambda: ufw_client.allow(port, proto, source),
    )


def preview_deny(port: int, proto: str, source: str | None) -> PreviewedChange:
    _validate_port(port)
    proto = _validate_proto(proto)
    source = _validate_source(source)

    warning = None
    if port == SSH_PORT and proto == "tcp":
        warning = (
            "This blocks port 22/tcp (SSH). If you're connected over SSH right now, this can "
            "end your session and lock you out until you have physical access to this machine."
        )

    return PreviewedChange(
        description=_describe("deny", "blocked", port, proto, source),
        warning=warning,
        apply=lambda: ufw_client.deny(port, proto, source),
    )


def preview_delete(rule_number: int) -> PreviewedChange:
    return PreviewedChange(
        description=(
            f"This will run: sudo ufw --force delete {rule_number}\n"
            f"Effect: removes rule #{rule_number} shown by `raven fw status`."
        ),
        warning=None,
        apply=lambda: ufw_client.delete_rule(rule_number),
    )


def preview_enable() -> PreviewedChange:
    warning = None
    if not ufw_client.is_ssh_allowed():
        warning = (
            "SSH (port 22/tcp) is not currently allowed. Enabling the firewall now could drop "
            "your SSH session and lock you out until you have physical access to this machine."
        )
    return PreviewedChange(
        description=(
            "This will run: sudo ufw --force enable\n"
            "Effect: the firewall becomes active; any connection not explicitly allowed is blocked by default."
        ),
        warning=warning,
        apply=ufw_client.enable,
    )


def preview_disable() -> PreviewedChange:
    return PreviewedChange(
        description=(
            "This will run: sudo ufw disable\n"
            "Effect: the firewall stops filtering entirely — every port becomes reachable as if no firewall existed."
        ),
        warning="Disabling removes ALL protection this firewall was providing, not just one rule.",
        apply=ufw_client.disable,
    )
