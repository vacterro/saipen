"""Content-based credential gate for handoff/AUDAPACK exports.

Path-based containment (``distribution.is_non_exportable_path``) refuses known
dump shapes.  This module closes the second half: it scans the BYTES selected
for export and refuses real credentials, while allowing the fixture/sentinel
tokens that the project's own tests rely on.  Findings are digest-only: values
are never returned or printed.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CredentialFinding:
    path: str
    pattern: str
    blob_sha256: str
    occurrences: int

    def diagnostic(self) -> str:
        return f"{self.path}: {self.pattern} x{self.occurrences} sha256:{self.blob_sha256[:16]}"


# Shape detectors.  These deliberately require the surrounding assignment or
# a non-fixture body so test fixtures such as `sk-live-SECRET-VALUE` and
# `ghp_abcdefgh...` remain exportable.
_PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    ("EXA_API_KEY_ASSIGNMENT", re.compile(rb"EXA_API_KEY\s*[:=]\s*[\"']?(?!exa-(?:SYNTHETIC|TEST|SENTINEL|EXAMPLE))[A-Za-z0-9_\-]{16,}")),
    ("OPENAI_LIVE_KEY", re.compile(rb"\bsk-(?!live-|ant-|1234|test|dummy|example)[A-Za-z0-9]{20,}\b")),
    ("ANTHROPIC_LIVE_KEY", re.compile(rb"\bsk-ant-(?!SENTINEL|TEST|EXAMPLE)[A-Za-z0-9]{16,}\b")),
    ("GITHUB_LIVE_TOKEN", re.compile(rb"\bgh[pousr]_(?!abcdefgh|012345|test|dummy)[A-Za-z0-9]{20,}\b")),
    ("AWS_ACCESS_KEY", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{12,}\b")),
    ("SLACK_TOKEN", re.compile(rb"\bxox[baprs]-(?!TEST|EXAMPLE)[A-Za-z0-9-]{10,}\b")),
    ("PRIVATE_KEY_BLOCK", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("BEARER_CREDENTIAL", re.compile(rb"Bearer\s+(?!test|dummy|example)[A-Za-z0-9._-]{24,}")),
)


# The detector's own source and its synthetic test fixture necessarily contain
# the pattern text. They are scanner code, not credentials.
_SELF_SCAN_EXEMPT = ("export_security.py", "content_scan.py")


def scan_bytes(path: str, data: bytes) -> list[CredentialFinding]:
    """Return digest-only findings for one export member's bytes."""
    if any(name in path for name in _SELF_SCAN_EXEMPT):
        return []
    digest = hashlib.sha256(data).hexdigest()
    findings: list[CredentialFinding] = []
    for name, rx in _PATTERNS:
        count = len(rx.findall(data))
        if count:
            findings.append(CredentialFinding(path, name, digest, count))
    return findings


def scan_export_members(project_root, members) -> list[CredentialFinding]:
    """Scan the exact members selected for export. Never opens other paths."""
    root = project_root if hasattr(project_root, "joinpath") else Path(project_root)
    findings: list[CredentialFinding] = []
    for rel in members:
        target = root / rel
        try:
            data = target.read_bytes()
        except OSError:
            continue
        findings.extend(scan_bytes(str(rel), data))
    return findings
