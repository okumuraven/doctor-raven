"""Wrappers around rkhunter, lynis, and clamscan for quick local security posture checks."""

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScanResult:
    tool: str
    installed: bool
    ok: bool
    summary: str


def _tool_missing(tool: str) -> ScanResult:
    return ScanResult(tool=tool, installed=False, ok=False, summary=f"{tool} not installed — run `raven doctor`")


def run_rkhunter() -> ScanResult:
    if not shutil.which("rkhunter"):
        return _tool_missing("rkhunter")

    result = subprocess.run(
        ["sudo", "rkhunter", "--check", "--skip-keypress", "--report-warnings-only"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    output = result.stdout + result.stderr
    warnings = len(re.findall(r"Warning:", output))
    ok = warnings == 0
    summary = "no warnings" if ok else f"{warnings} warning(s) — see full output with `rkhunter --check`"
    return ScanResult(tool="rkhunter", installed=True, ok=ok, summary=summary)


def run_lynis() -> ScanResult:
    if not shutil.which("lynis"):
        return _tool_missing("lynis")

    result = subprocess.run(
        ["lynis", "audit", "system", "--quick", "--no-colors"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    output = result.stdout + result.stderr
    warn_match = re.search(r"Warnings?\s*\((\d+)\)", output)
    suggest_match = re.search(r"Suggestions?\s*\((\d+)\)", output)
    warnings = int(warn_match.group(1)) if warn_match else 0
    suggestions = int(suggest_match.group(1)) if suggest_match else 0
    ok = warnings == 0
    summary = f"{warnings} warning(s), {suggestions} suggestion(s)"
    return ScanResult(tool="lynis", installed=True, ok=ok, summary=summary)


def run_clamscan(paths: list[str] | None = None) -> ScanResult:
    if not shutil.which("clamscan"):
        return _tool_missing("clamscan")

    targets = paths or [str(Path.home() / "Downloads")]
    existing_targets = [t for t in targets if Path(t).exists()]
    if not existing_targets:
        return ScanResult(tool="clamscan", installed=True, ok=True, summary="no target paths existed, skipped")

    result = subprocess.run(
        ["clamscan", "-r", "--infected", "--quiet", *existing_targets],
        capture_output=True,
        text=True,
        timeout=900,
    )
    infected_lines = [line for line in result.stdout.splitlines() if "FOUND" in line]
    ok = result.returncode == 0
    summary = "clean" if ok else f"{len(infected_lines)} infected file(s) found: {', '.join(infected_lines[:5])}"
    return ScanResult(tool="clamscan", installed=True, ok=ok, summary=summary)


def run_all(clamscan_paths: list[str] | None = None) -> list[ScanResult]:
    return [run_rkhunter(), run_lynis(), run_clamscan(clamscan_paths)]
