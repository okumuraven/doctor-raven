"""Regex-based secret detection over a unified diff (only newly-added lines are flagged, so
history that predates this commit doesn't re-trigger every time) and over staged filenames.
This is a safety net, not a guarantee — it catches common, obvious cases; it will not catch
every possible secret shape. Never prints a full matched secret back to the terminal."""

import re

from doctor_raven.features.git_ops.models import SecretFinding

SENSITIVE_FILENAME_PATTERNS = [
    re.compile(r"(^|/)\.env(\..*)?$"),
    re.compile(r"(^|/)id_(rsa|ed25519|dsa|ecdsa)$"),
    re.compile(r"\.(pem|pfx|p12|key)$"),
    re.compile(r"(^|/)credentials\.json$"),
    re.compile(r"(^|/)service[_-]account.*\.json$"),
]
SENSITIVE_FILENAME_EXCEPTIONS = [re.compile(r"\.env\.(example|sample|template)$")]

# Test/fixture files routinely contain deliberately fake credentials to exercise this exact
# scanner — content there is exempt from the content patterns below (filenames are still
# checked regardless: a real .env sitting in a test dir is still worth flagging).
TEST_PATH_PATTERNS = [
    re.compile(r"(^|/)tests?/"),
    re.compile(r"(^|/)test_[^/]+\.py$"),
    re.compile(r"[^/]+_test\.py$"),
    re.compile(r"(^|/)__tests__/"),
    re.compile(r"(^|/)(spec|fixtures)/"),
]

SECRET_CONTENT_PATTERNS = [
    ("private key header", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "generic secret assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|passwd|access[_-]?key|private[_-]?key)\b"
            r"\s*[:=]\s*['\"][A-Za-z0-9_\-/+=]{8,}['\"]"
        ),
    ),
]


def _redact(matched_text: str) -> str:
    if len(matched_text) <= 8:
        return "*" * len(matched_text)
    return f"{matched_text[:4]}…redacted…{matched_text[-2:]}"


def is_sensitive_filename(path: str) -> bool:
    if any(pattern.search(path) for pattern in SENSITIVE_FILENAME_EXCEPTIONS):
        return False
    return any(pattern.search(path) for pattern in SENSITIVE_FILENAME_PATTERNS)


def is_test_path(path: str) -> bool:
    return any(pattern.search(path) for pattern in TEST_PATH_PATTERNS)


def scan_filenames(paths: list[str]) -> list[SecretFinding]:
    return [SecretFinding(file=path, line=None, kind="sensitive filename", preview=path) for path in paths if is_sensitive_filename(path)]


def scan_diff(diff_text: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    current_file = "?"
    line_no: int | None = None

    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            current_file = line[4:].removeprefix("b/")
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            line_no = int(match.group(1)) if match else None
            continue
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            continue  # removed line — doesn't exist in the new file, don't advance the counter
        if line.startswith("+"):
            added_content = line[1:]
            if not is_test_path(current_file):
                for kind, pattern in SECRET_CONTENT_PATTERNS:
                    match = pattern.search(added_content)
                    if match:
                        findings.append(SecretFinding(file=current_file, line=line_no, kind=kind, preview=_redact(match.group(0))))
            if line_no is not None:
                line_no += 1
        elif line.startswith(" ") and line_no is not None:
            line_no += 1

    return findings
