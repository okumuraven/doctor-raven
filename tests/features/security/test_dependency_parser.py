import json

import pytest

from doctor_raven.features.security import dependency_parser


def test_parse_requirements_skips_comments_blank_lines_and_editable_installs(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("# comment\n\nrequests==2.34.2\ntyper==0.12.0  # inline comment\n-e .\n")

    assert dependency_parser.parse_requirements(req) == [("requests", "2.34.2"), ("typer", "0.12.0")]


def test_parse_package_lock_v2_skips_root_package(tmp_path):
    lock = tmp_path / "package-lock.json"
    lock.write_text(json.dumps({"packages": {"": {"name": "root"}, "node_modules/lodash": {"version": "4.17.21"}}}))

    assert dependency_parser.parse_package_lock(lock) == [("lodash", "4.17.21")]


def test_parse_package_lock_v1(tmp_path):
    lock = tmp_path / "package-lock.json"
    lock.write_text(json.dumps({"dependencies": {"lodash": {"version": "4.17.21"}}}))

    assert dependency_parser.parse_package_lock(lock) == [("lodash", "4.17.21")]


def test_detect_and_parse_rejects_unsupported_filename(tmp_path):
    other = tmp_path / "Pipfile.lock"
    other.write_text("{}")

    with pytest.raises(ValueError):
        dependency_parser.detect_and_parse(other)


def test_detect_and_parse_requirements(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("requests==2.34.2\n")

    ecosystem, deps = dependency_parser.detect_and_parse(req)
    assert ecosystem == "PyPI"
    assert deps == [("requests", "2.34.2")]
