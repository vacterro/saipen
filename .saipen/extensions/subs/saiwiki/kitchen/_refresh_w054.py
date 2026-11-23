"""saiwiki W-054 FORCE-FRESH pass: zero-drift verification.

The freshness triple is unchanged since W-053 and the last collect settled the
READY record, so this pass asserts the absence of drift instead of applying
edits: the triple must still equal the settled W-053 binding, all 9 payload
pages must be byte-identical to the settled record, all 55 read dependencies
must be unchanged, and the Scenarios mirror marker must still name the
canonical corpus digest. Any mismatch is a hard failure -- drift would mean a
real refresh, not this pass. Writes nothing.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "tools"))

from freshness import compute_role_revision, compute_source_identity  # noqa: E402

SETTLED = (
    ROOT
    / ".saipen/extensions/subs/saiwiki/SETTLED"
    / "sha256_bc0d96eb94f47073f603c0e503a3dcae67fdd80eca54a55d33f5fd96a97174e5.json"
)
SCENARIOS = ROOT / ".saipen/extensions/subs/saiwiki/kitchen/wiki/Scenarios.md"
MIRROR_DIGEST = "f46193d66010358e"


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    record = json.loads(SETTLED.read_text(encoding="utf-8"))
    identity = compute_source_identity(ROOT)
    role_revision = compute_role_revision(str(ROOT / ".saipen/extensions/subs/saiwiki.md"))

    checks = {
        "source_head": identity.source_head == record["base_source_head"],
        "source_tree_fingerprint": (
            identity.source_tree_fingerprint == record["base_source_tree_fingerprint"]
        ),
        "discovery_model": identity.discovery_model == record["base_discovery_model"],
        "role_revision": role_revision == record["role_revision"],
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise AssertionError(f"triple moved past the settled W-053 binding: {failed}")

    payload_drift = [
        rel
        for rel, want in sorted(record["payload_hashes"].items())
        if sha256_file(ROOT / rel) != want
    ]
    read_drift = [
        rel
        for rel, want in sorted(record["read_set"].items())
        if sha256_file(ROOT / rel) != want
    ]
    if payload_drift or read_drift:
        raise AssertionError(
            f"drift found: payload={payload_drift} read_set={read_drift}"
        )

    scenarios = SCENARIOS.read_text(encoding="utf-8")
    marker = f"<!-- mirrors: CONFORMANCE.md rows 1-257 sha256:{MIRROR_DIGEST} -->"
    if marker not in scenarios:
        raise AssertionError("Scenarios mirror marker missing or moved")

    print(
        json.dumps(
            {
                "applied": [],
                "already": 0,
                "drift": 0,
                "payload_count": len(record["payload_hashes"]),
                "read_count": len(record["read_set"]),
                "role_revision": role_revision,
                "scenarios": f"rows 1-257 marker digest sha256:{MIRROR_DIGEST} intact",
                "source_head": identity.source_head,
                "source_tree_fingerprint": identity.source_tree_fingerprint,
                "verdict": "ZERO-DRIFT: every page byte-identical to the settled W-053 payload",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
