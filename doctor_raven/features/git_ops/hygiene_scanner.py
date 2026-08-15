"""Catches common repo-hygiene mistakes the secrets scanner was never meant to catch: build
artifacts and generated files that almost always shouldn't be tracked, and a missing/empty
.gitignore that let them slip through in the first place. Soft warnings, not a hard block —
tracking a stray .pyc file isn't a security risk, just worth a heads-up before it's committed."""

import re
from dataclasses import dataclass
from pathlib import Path

IGNORE_WORTHY_PATTERNS = [
    ("compiled Python bytecode", re.compile(r"(^|/)__pycache__/")),
    ("compiled Python bytecode", re.compile(r"\.pyc$")),
    ("compiled Python bytecode", re.compile(r"\.pyo$")),
    ("Python packaging metadata", re.compile(r"\.egg-info/")),
    ("Node.js dependencies", re.compile(r"(^|/)node_modules/")),
    ("macOS Finder cruft", re.compile(r"(^|/)\.DS_Store$")),
    ("build output", re.compile(r"(^|/)(dist|build)/")),
    ("compiled Java bytecode", re.compile(r"\.class$")),
    ("Python virtual environment", re.compile(r"(^|/)(\.venv|venv)/")),
    ("test/type-check cache", re.compile(r"(^|/)(\.pytest_cache|\.mypy_cache|\.tox)/")),
]


@dataclass(frozen=True)
class HygieneFinding:
    file: str
    reason: str


def scan_staged_filenames(paths: list[str]) -> list[HygieneFinding]:
    findings = []
    for path in paths:
        for reason, pattern in IGNORE_WORTHY_PATTERNS:
            if pattern.search(path):
                findings.append(HygieneFinding(file=path, reason=reason))
                break
    return findings


def gitignore_warning(repo_root: Path) -> str | None:
    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.exists():
        return "No .gitignore found in this repo."
    if not gitignore_path.read_text().strip():
        return ".gitignore exists but is empty."
    return None
