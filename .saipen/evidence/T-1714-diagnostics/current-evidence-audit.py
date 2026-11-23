"""Check exact existing phase evidence before spending it on REVIEW."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import operations as ops
from saipen_engine import regression_execution as execution
from saipen_engine.core_unit import baseline_digest, ship_gate, tree_fingerprint

output = HERE / "current-evidence-audit.json"
if output.exists():
    raise RuntimeError("Evidence audit already exists")
docs, state, _board, _tail = ops._read(ROOT)
assert state["task"] == "T-1714" and state["phase"] == "VERIFY"
fingerprint = tree_fingerprint(ROOT)
assert fingerprint == "2df2566be72aeb7bde515aadf1891ccb56bd24500385b60c483656fa0259fcaa"
pair_error = execution.evidence_gate(ROOT, "T-1714", docs, state)
if pair_error is not None:
    raise RuntimeError(pair_error + "; audit runtime: " + sys.executable)
family_error = ship_gate(ROOT, "T-1714", docs["_history"].events)
if family_error is not None:
    raise RuntimeError(family_error)
ownership = json.loads((HERE / "owned-application-final.json").read_bytes())
for relative, record in ownership["paths"].items():
    for path, expected in ((ROOT / relative, record["after_sha256"]),
                           (ROOT / record["preserved_before"], record["before_sha256"]),
                           (ROOT / record["preserved_current"], record["after_sha256"])):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, str(path)
assert hashlib.sha256((HERE / "owned-changes-final.patch").read_bytes()).hexdigest() == ownership["patch_sha256"]
labels = ("verify-executed-pair-corrected", "verify-executed-pair-resumed", "verify-neighbors-corrected",
          "verify-source-contracts-corrected", "verify-lint-corrected",
          "verify-whitespace-corrected", "verify-native-core-corrected",
          "verify-current-done-reverify")
checked = {}
for label in labels:
    raw = (HERE / (label + ".json")).read_bytes()
    record = json.loads(raw)
    assert record["exit_code"] == 0 and record["phase"] == "VERIFY", label
    assert record["fingerprint"] == fingerprint and record["source_unchanged"] is True, label
    for stream in ("stdout", "stderr"):
        body = (HERE / (label + "." + stream + ".bin")).read_bytes()
        assert hashlib.sha256(body).hexdigest() == record[stream + "_sha256"], label
        assert body.decode("utf-8", errors="replace") == record[stream], label
    checked[label] = hashlib.sha256(raw).hexdigest()
family_path = ROOT / ".saipen/evidence/core-unit/2df2566be72aeb7b-20261011T115749Z.json"
family_raw = family_path.read_bytes()
assert hashlib.sha256(family_raw).hexdigest() == "7248d68608970513ac71965d9af5def9abf6eddfe4c54fa85dcd5e548ebadae8"
family = json.loads(family_raw)
assert family["fingerprint"] == fingerprint and family["baseline_sha256"] == baseline_digest(ROOT)
assert family["verdict"] == family["status"] == "PASS" and family["exit_code"] == 0
assert family["ran"] == family["discovered"] == sum(item["ran"] for item in family["shards"]) == 6207
assert not family["red"] and not family["new_red"] and not family["problems"]
source = ROOT / ".saipen/intake/active/SRC-205.md"
metadata = json.loads(source.with_suffix(".meta.json").read_bytes())
assert hashlib.sha256(source.read_bytes()).hexdigest() == metadata["source_sha256"]
value = {"ok": True, "work": "T-1714", "phase": "VERIFY", "fingerprint": fingerprint,
         "owned_paths": list(ownership["paths"]), "gate_record_sha256": checked,
         "family_record": str(family_path.relative_to(ROOT)), "family_ran": 6207,
         "family_new_red": 0, "current_executed_pair_admissible": True,
         "source_body_sha256": metadata["source_sha256"],
         "limits": "Checks current original records and hashes; adds no regression receipt, family execution or Source disposition. REVIEW and local no-publish finish remain due."}
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps(value))
