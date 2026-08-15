"""Parses dependency manifests into (name, version) pairs for CVE scanning."""

import json
import re
from pathlib import Path

REQUIREMENT_RE = re.compile(r"^([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.\-+]+)")


def parse_requirements(path: Path) -> list[tuple[str, str]]:
    deps = []
    for raw_line in path.read_text().splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = REQUIREMENT_RE.match(line)
        if match:
            deps.append((match.group(1), match.group(2)))
    return deps


def parse_package_lock(path: Path) -> list[tuple[str, str]]:
    data = json.loads(path.read_text())
    deps = []

    if "packages" in data:  # npm lockfile v2/v3
        for pkg_path, info in data["packages"].items():
            if not pkg_path or "node_modules/" not in pkg_path:
                continue
            name = pkg_path.split("node_modules/")[-1]
            version = info.get("version")
            if version:
                deps.append((name, version))
    elif "dependencies" in data:  # npm lockfile v1
        for name, info in data["dependencies"].items():
            version = info.get("version")
            if version:
                deps.append((name, version))

    return deps


def detect_and_parse(path: Path) -> tuple[str, list[tuple[str, str]]]:
    """Returns (ecosystem, [(name, version), ...]) based on the manifest filename."""
    if path.name == "requirements.txt":
        return "PyPI", parse_requirements(path)
    if path.name in ("package-lock.json", "npm-shrinkwrap.json"):
        return "npm", parse_package_lock(path)

    raise ValueError(f"Unsupported dependency file: {path.name} (expected requirements.txt or package-lock.json)")
