"""Read-only compatibility evidence for the next queued Work; no mutation."""

import collections
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine import findings  # noqa: E402

messages = [
    "cross-doc drift [root-file-set] -- unexpected root files: ['T-1446', 'tuple[bool']",
    "cross-doc drift [release-version] -- mismatch in T-1446",
]
cases = [findings.classify("problem", message) for message in messages]


def rows(value):
    if isinstance(value, dict):
        if value.get("rule_id") == "cross_doc_drift":
            yield value
        for child in value.values():
            yield from rows(child)
    elif isinstance(value, list):
        for child in value:
            yield from rows(child)


scope = root / ".saipen/recovery/conformance/debt"
versions = collections.Counter()
affected = []
errors = []
paths = sorted(scope.glob("*.json"))
for path in paths:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append({"path": path.name, "error": type(exc).__name__})
        continue
    versions[str(doc.get("ruleset_version"))] += 1
    matched = [row for row in rows(doc) if re.search(r"T-\d+|SRC-\d+|E-\d+", str(row.get("detail") or ""))]
    if matched:
        affected.append({"path": path.name, "finding_count": len(matched)})

print(json.dumps({
    "scope": str(scope.relative_to(root)),
    "files_read": len(paths) - len(errors),
    "errors": errors,
    "ruleset_versions": versions,
    "current_ruleset_version": findings.RULESET_VERSION,
    "current_ruleset_fingerprint": findings.ruleset_fingerprint(),
    "different_subtypes_collide": cases[0]["detail_hash"] == cases[1]["detail_hash"],
    "case_details": [case["detail"] for case in cases],
    "affected_local_snapshots": affected,
    "limit": "Only this explicit project's stored debt directory was read. No all-project compatibility claim, canonical mutation or operator choice is implied.",
}, indent=2))
