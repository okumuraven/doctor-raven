"""Orchestrates single-package CVE lookups and whole-manifest dependency scans."""

from dataclasses import dataclass
from pathlib import Path

from doctor_raven.features.security import osv_client
from doctor_raven.features.security.dependency_parser import detect_and_parse


@dataclass(frozen=True)
class DependencyFinding:
    ecosystem: str
    name: str
    version: str
    vuln_ids: list[str]

    @property
    def vulnerable(self) -> bool:
        return len(self.vuln_ids) > 0


def check_package(ecosystem: str, name: str, version: str) -> list[dict]:
    return osv_client.query_single(ecosystem, name, version)


def scan_dependency_file(path: Path, batch_size: int = 100) -> list[DependencyFinding]:
    ecosystem, deps = detect_and_parse(path)
    if not deps:
        return []

    findings: list[DependencyFinding] = []
    for start in range(0, len(deps), batch_size):
        chunk = deps[start : start + batch_size]
        packages = [(ecosystem, name, version) for name, version in chunk]
        vuln_id_lists = osv_client.query_batch(packages)
        for (name, version), vuln_ids in zip(chunk, vuln_id_lists):
            findings.append(DependencyFinding(ecosystem=ecosystem, name=name, version=version, vuln_ids=vuln_ids))

    return findings
