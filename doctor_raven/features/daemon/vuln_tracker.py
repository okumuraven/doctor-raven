"""Dedup store for the daemon's dependency/CVE watch — a vulnerability only triggers a
notification the first time it's seen for a given project/package/version, never again."""

from doctor_raven.core.db import get_conn
from doctor_raven.features.security.cve import DependencyFinding


def filter_new_vulnerabilities(
    project_name: str, findings: list[DependencyFinding]
) -> list[tuple[DependencyFinding, str]]:
    new_pairs: list[tuple[DependencyFinding, str]] = []
    with get_conn() as conn:
        for finding in findings:
            for vuln_id in finding.vuln_ids:
                row = conn.execute(
                    "SELECT 1 FROM known_vulnerabilities WHERE project_name = ? AND package_name = ? "
                    "AND version = ? AND vuln_id = ?",
                    (project_name, finding.name, finding.version, vuln_id),
                ).fetchone()
                if row is None:
                    new_pairs.append((finding, vuln_id))
    return new_pairs


def record_seen(project_name: str, pairs: list[tuple[DependencyFinding, str]]) -> None:
    with get_conn() as conn:
        for finding, vuln_id in pairs:
            conn.execute(
                "INSERT OR IGNORE INTO known_vulnerabilities (project_name, package_name, version, vuln_id) "
                "VALUES (?, ?, ?, ?)",
                (project_name, finding.name, finding.version, vuln_id),
            )
