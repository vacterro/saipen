"""Read current campaign batch provenance; never mutate canonical records."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine import closure, core_unit

registry_path = closure.registry_path(root)
before = registry_path.read_bytes()
registry = closure.read_registry(root)
rows = []
for number in range(7, 13):
    identity = f"C-{number:03d}"
    cohort = registry["cohorts"][identity]
    try:
        closure.cohort_scope(cohort)
        scope_error = None
    except ValueError as exc:
        scope_error = str(exc)
    rows.append({"cohort": identity, "publication_status": cohort["publication_status"],
                 "members": sorted(cohort["members"]),
                 "readiness": closure.cohort_readiness(root, cohort),
                 "internal_scope_error": scope_error,
                 "live_member_mismatches": closure.cohort_member_mismatches(root, cohort)})
if registry_path.read_bytes() != before:
    raise RuntimeError("read-only cohort audit changed registry bytes")
report = {"scope": "C-007 through C-012, current source versus historical reviewed members",
          "fingerprint": core_unit.tree_fingerprint(root),
          "registry_sha256": hashlib.sha256(before).hexdigest(),
          "registry_unchanged": True, "cohorts": rows,
          "note": "readiness proves local member closure; it is not a current-byte or publication verdict"}
(Path(__file__).parent / "cohort-audit-20261020.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"fingerprint": report["fingerprint"],
                  "mismatches": {row["cohort"]: len(row["live_member_mismatches"]) for row in rows},
                  "registry_unchanged": True}))
