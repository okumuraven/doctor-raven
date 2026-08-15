"""Startup banner shown on bare `raven` and at the top of the morning briefing —
ties a bit of personality to a live system glimpse rather than being pure decoration."""

from datetime import datetime

from rich.console import Group
from rich.text import Text

from doctor_raven.config import Config
from doctor_raven.features import system_health
from doctor_raven.util.formatting import console

RAVEN_ART = r"""
     \\\\               ////
      \\\\             ////
       \\\\           ////
        \\\\_________////
          \    (o)    /
           \_________/
                | |
"""

HEALTH_MARKERS = {"normal": "●", "hot": "▲", "critical": "■"}


def _time_greeting(hour: int) -> str:
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    if 17 <= hour < 21:
        return "Good evening"
    return "Still up"


def _health_glimpse(config: Config) -> str:
    try:
        status = system_health.read_status()
        decision = system_health.evaluate(status, config)
    except Exception:  # sensors unavailable, sandboxed env, etc. — banner should never crash on this
        return "system status unavailable"

    temp = f"{status.cpu_temp_c:.0f}°C" if status.cpu_temp_c is not None else "n/a"
    marker = HEALTH_MARKERS[decision.level]
    return f"{marker} {temp} · load {status.load_per_core:.2f}/core · {decision.level}"


def build_banner(config: Config) -> Group:
    greeting = _time_greeting(datetime.now().hour)
    return Group(
        Text(RAVEN_ART, style="bold red"),
        Text("  D O C T O R   R A V E N", style="bold bright_magenta"),
        Text("  ══════════════════════════════", style="dim"),
        Text(f"  {greeting}, {config.user_name}. Local-first. Cyber-aware. Always watching.", style="bold cyan"),
        Text(f"  {_health_glimpse(config)}", style="dim"),
    )


def print_banner(config: Config) -> None:
    console.print(build_banner(config))
    console.print()
