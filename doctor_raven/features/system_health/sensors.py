"""Raw CPU thermal/load readings. No policy here — see guard.py for thresholds."""

import os
from pathlib import Path

THERMAL_ROOT = Path("/sys/class/thermal")
PREFERRED_ZONE_TYPES = ("x86_pkg_temp", "coretemp", "cpu_thermal", "soc_thermal")


def _read_zone_temp_c(zone: Path) -> float | None:
    try:
        raw = (zone / "temp").read_text().strip()
        return int(raw) / 1000.0
    except (OSError, ValueError):
        return None


def read_cpu_temp_c() -> float | None:
    """Best-effort CPU package temperature. Prefers the actual package sensor over
    generic ACPI zones (chassis/wifi/etc.), falling back to the hottest zone found."""
    if not THERMAL_ROOT.exists():
        return None

    readings: dict[str, float] = {}
    for zone in THERMAL_ROOT.glob("thermal_zone*"):
        try:
            zone_type = (zone / "type").read_text().strip()
        except OSError:
            continue
        temp = _read_zone_temp_c(zone)
        if temp is not None and temp > 0:
            readings[zone_type] = temp

    for preferred in PREFERRED_ZONE_TYPES:
        if preferred in readings:
            return readings[preferred]

    return max(readings.values()) if readings else None


def read_load_1m() -> float:
    return os.getloadavg()[0]


def cpu_count() -> int:
    return os.cpu_count() or 1
