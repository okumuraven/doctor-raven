from pathlib import Path

from doctor_raven.features.system_health import sensors


def _make_zone(root: Path, idx: int, zone_type: str, temp_millideg: int) -> None:
    zone_dir = root / f"thermal_zone{idx}"
    zone_dir.mkdir()
    (zone_dir / "type").write_text(zone_type)
    (zone_dir / "temp").write_text(str(temp_millideg))


def test_prefers_package_sensor_over_generic_zones(tmp_path, monkeypatch):
    monkeypatch.setattr(sensors, "THERMAL_ROOT", tmp_path)
    _make_zone(tmp_path, 0, "acpitz", 40000)
    _make_zone(tmp_path, 1, "x86_pkg_temp", 65000)

    assert sensors.read_cpu_temp_c() == 65.0


def test_falls_back_to_hottest_zone_when_no_preferred_type(tmp_path, monkeypatch):
    monkeypatch.setattr(sensors, "THERMAL_ROOT", tmp_path)
    _make_zone(tmp_path, 0, "acpitz", 40000)
    _make_zone(tmp_path, 1, "iwlwifi_1", 55000)

    assert sensors.read_cpu_temp_c() == 55.0


def test_returns_none_when_thermal_root_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sensors, "THERMAL_ROOT", tmp_path / "does-not-exist")
    assert sensors.read_cpu_temp_c() is None


def test_ignores_zero_readings(tmp_path, monkeypatch):
    monkeypatch.setattr(sensors, "THERMAL_ROOT", tmp_path)
    _make_zone(tmp_path, 0, "acpitz", 0)
    _make_zone(tmp_path, 1, "acpitz2", 30000)

    assert sensors.read_cpu_temp_c() == 30.0
