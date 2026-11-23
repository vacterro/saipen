"""Structural and artifact-integrity checks; semantic review remains separate."""
from __future__ import annotations
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import tree_fingerprint

METRICS = {"FALSE_BLOCK_RATE", "AUTONOMOUS_CONTINUITY_RATE", "RECOVERY_SUCCESS_RATE",
           "OPERATOR_INTERRUPTS_PER_100_TICKETS", "BLOCKER_RECURRENCE_RATE",
           "MEAN_RECOVERY_TIME", "INTEGRITY_VIOLATION_RATE"}
CLASSES = {"True integrity or security violation", "Missing authorization",
           "Unsupported runtime capability", "Temporary infrastructure failure",
           "Stale or incompatible evidence", "Recoverable state divergence",
           "Resource or claim contention", "Test or environment failure",
           "Consumer implementation defect", "Protocol implementation defect",
           "Incorrect refusal", "Undetermined, needs investigation"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(report, mapping):
    errors = []
    headings = [int(value) for value in re.findall(r"^## (\d+)\. ", report, re.M)]
    if headings != list(range(1, 17)):
        errors.append("sixteen ordered report sections")
    rows = [line.split("|")[1:-1] for line in report.splitlines() if line.startswith("| ")]
    taxonomy = {row[0].strip() for row in rows if row[0].strip() in CLASSES}
    if taxonomy != CLASSES:
        errors.append("twelve blocker classes")
    if any(len(row) != 5 or any(not cell.strip() for cell in row)
           for row in rows if row[0].strip() in CLASSES):
        errors.append("complete taxonomy cells")
    metrics = {row[0].strip() for row in rows if row[0].strip() in METRICS}
    if metrics != METRICS:
        errors.append("seven KPI definitions")
    if any(len(row) != 5 or any(not cell.strip() for cell in row)
           for row in rows if row[0].strip() in METRICS):
        errors.append("complete KPI cells")
    if [int(value) for value in re.findall(r"^\*\*Q([1-6]) — ", report, re.M)] != list(range(1, 7)):
        errors.append("six explicit decisions")
    contract = json.loads((ROOT / ".saipen/intake/contracts/SRC-215.json").read_text(encoding="utf-8"))
    expected = {key.rsplit(":", 1)[1] for key in contract["clauses"]}
    if set(mapping["clauses"]) != expected or len(expected) != 16:
        errors.append("all sixteen source clauses")
    source = ROOT / ".saipen/intake/active/SRC-215.md"
    if mapping["source_sha256"] != sha(source) or mapping["source_sha256"] != contract["source_sha256"]:
        errors.append("exact source identity")
    for clause, value in mapping["clauses"].items():
        if not value["sections"] or any(number not in headings for number in value["sections"]):
            errors.append(f"mapped report sections {clause}")
        for relative in value["evidence"]:
            path = (HERE / relative).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                errors.append(f"available evidence {clause}: {relative}")
    return errors


label = sys.argv[1]
assert re.fullmatch(r"[a-z0-9-]+", label)
output = HERE / (label + ".json")
assert not output.exists()
report = (HERE / "REPORT.md").read_text(encoding="utf-8")
mapping = json.loads((HERE / "coverage-map.json").read_text(encoding="utf-8"))
errors = check(report, mapping)
assert not errors, errors
bad = {
    "missing_section": check(report.replace("## 8. Safe continuation", "## Missing. Safe continuation"), mapping),
    "missing_metric": check("\n".join(line for line in report.splitlines()
                                       if not line.startswith("| INTEGRITY_VIOLATION_RATE |")), mapping),
    "wrong_source_identity": check(report, {**mapping, "source_sha256": "0" * 64}),
}
assert all(bad.values()), bad
catalog = json.loads((HERE / "source-catalog.json").read_text(encoding="utf-8"))
for relative, record in catalog["files"].items():
    assert sha(ROOT / relative) == record["sha256"], relative
assert tree_fingerprint(ROOT) == catalog["source_fingerprint"]
controls = json.loads((HERE / "controls.json").read_text(encoding="utf-8"))
assert controls["passed"] and controls["production_unchanged"]
consumers = json.loads((HERE / "consumer-current.json").read_text(encoding="utf-8"))
consumer_observation = {}
for name, consumer in consumers["consumers"].items():
    assert consumer["canonical_and_history_unchanged"]
    changed = [basename for basename, digest in consumer["canonical_sha256"].items()
               if sha(Path(consumer["root"]) / ".saipen" / basename) != digest]
    # Other authorized sessions may progress after a bounded read-only probe.
    # That does not prove this audit mutated them, or invalidate historical
    # observations. Explicit temporal qualification is required in the report.
    if changed:
        assert "point-in-time" in report and "T-927" in report
    consumer_observation[name] = {"unchanged_during_probe": True,
                                  "changed_since_probe": changed,
                                  "checked_utc": consumers["checked_utc"]}
roadmap = (HERE / "ROADMAP.md").read_text(encoding="utf-8")
assert re.findall(r"^## (RSL-\d+) —", roadmap, re.M) == [f"RSL-{i:02d}" for i in range(1, 9)]
assert "existing T-1715" in roadmap and "not executed" in roadmap
artifacts = {str((HERE / name).relative_to(ROOT)): sha(HERE / name)
             for name in ("REPORT.md", "ROADMAP.md", "coverage-map.json", "controls.json",
                          "source-catalog.json", "consumer-current.json", "consumer-refresh.json",
                          "build-root-status.json")}
value = {"passed": True, "source_fingerprint": catalog["source_fingerprint"],
         "sections": 16, "clauses": 16, "blocker_classes": 12, "metrics": 7,
         "decisions": 6, "roadmap_items": 8, "known_bad_controls": bad,
         "consumer_observations": consumer_observation, "catalog_files_current": len(catalog["files"]),
         "artifact_sha256": artifacts,
         "limit": "structural coverage and byte integrity only; independent semantic review required"}
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value[key] for key in ("passed", "clauses", "sections", "blocker_classes", "metrics", "decisions")}))
