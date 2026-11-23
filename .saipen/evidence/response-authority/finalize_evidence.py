"""Finalize the evidence projection; never write protected protocol state."""
from pathlib import Path
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import tree_fingerprint
from saipen_engine.oracle import oracle_digest, verifier_identity

def proof(relative):
    return {"path": relative, "sha256": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()}

data = json.loads((HERE / "acceptance-map.json").read_text(encoding="utf-8-sig"))
rows = data["clauses"]
for row in rows.values():
    for item in row["proof"]:
        assert proof(item["path"])["sha256"] == item["sha256"], item["path"]

record_path = ".saipen/evidence/core-unit/1d9268ada530735b-20261003T040639Z.json"
record = json.loads((ROOT / record_path).read_text(encoding="utf-8-sig"))
assert record["fingerprint"] == tree_fingerprint(ROOT)
assert record["status"] == "PASS" and record["ran"] == record["discovered"] == 4770 and not record["red"]
validation_path = ".saipen/evidence/response-authority/validate-final-current.json"
validation = json.loads((ROOT / validation_path).read_text(encoding="utf-8-sig"))
assert validation["ok"] and validation["conformance_status"]["status"] == "CURRENT_PASS"
receipt = validation["conformance_status"]["receipt"]
assert receipt["blocking_findings"]["problem_count"] == 0

paired = json.loads((HERE / "paired/live.json").read_text())
assert verifier_identity(paired["command"], paired["oracle_paths"], ROOT) == paired["verifier"]
assert oracle_digest(ROOT, paired["production_paths"]) == paired["subject_digest"]
assert paired["returncode"] == 0

for clause, path, conclusion, verification in (
    ("SRC-165:R032", validation_path, "Actual final canonical validator: CURRENT_PASS, zero blocking problems; 31 retained warnings.", "bin/saipen.cmd validate --json -> CURRENT_PASS, receipt-d48e15f7a627"),
    ("SRC-165:R033", record_path, "Actual fresh complete declared family matches the final tree: 4770 tests, red=0, new_red=0; no leaked sandboxes.", "python -B tools/core_unit.py evidence T-1600 --jobs 6 --fresh -> PASS, final fingerprint 1d9268ada530735b"),
):
    rows[clause].update(status="VERIFIED", conclusion=conclusion, verification=verification, proof=[proof(path)])

(HERE / "acceptance-map.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
(HERE / "FINAL.md").write_text("""# T-1600 final evidence supplement

The historical REVIEW.md and all pinned oracle/installed-route proofs are
preserved. This supplement records the final subject after the budget and
literal-contract findings were repaired without changing the checkers.

* Complete fresh family: 4770 discovered and run; red=0, new_red=0.
  Record: `.saipen/evidence/core-unit/1d9268ada530735b-20261003T040639Z.json`.
  Final tested-tree fingerprint: `1d9268ada530735b67ae68d1a55f5205919a679d5817bdf2e83fa24ab4f3449e`.
* Canonical conformance: CURRENT_PASS, zero blocking problems, 31 retained
  warnings; `validate-final-current.json`, receipt-d48e15f7a627.
* Identical paired ingress/digest/delivery oracle: verifier
  `12b954a7d9c4664a`, pre-fix subject `f6bbc6071e5b3db9` is RED;
  current subject `56e4c53352b2ff2e` is GREEN (34 tests).
* Fixed ceilings remain unchanged: CORE normalized 31339 bytes;
  ordinary phase 40012/40960; human markdown 308220/308224.
  The final 51 affected-module checks pass in budget-final-tests.txt.
* Canonical source coverage is complete: SRC-165 36/36 clauses and
  SRC-166 5/5 clauses. Canonical source bodies and provenance are unchanged.
* Installed OpenCode completed-part enforcement passed three fresh pressures;
  Codex standalone Stop correction and Claude admission refusal are separate
  findings. Live host trust/load, hot reload, and Claude downstream response
  admission remain NOT_PROVEN/UNAVAILABLE. No synthetic signing was granted.
* SRC-165 forbids release publication. Evidence closure may bind the actual
  shared unpublished implementation to a pending cohort; it cannot claim
  published bytes. The parent T-1510 still owes its own canonical lifecycle
  and final zero-change blocker reconciliation.

Memory promotion: NO. This work confirms existing authority, renderer,
same-oracle and source-coverage rules; no distinct reusable lesson is needed.
""", encoding="utf-8")
print(json.dumps({"ok": True, "clauses": len(rows), "fingerprint": record["fingerprint"], "verifier": paired["verifier"]}))
