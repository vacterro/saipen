"""Independently remeasure the exact admitted pair; REVIEW mints no authority."""
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
from saipen_engine.core_unit import tree_fingerprint

output = HERE / "review-pair.json"
if output.exists():
    raise RuntimeError("independent review evidence already exists")
docs, state, _board, _tail = ops._read(ROOT)
if state.get("task") != "T-1714" or state.get("phase") != "REVIEW":
    raise RuntimeError("T-1714 does not own REVIEW")
gate = execution.evidence_gate(ROOT, "T-1714", docs, state)
if gate is not None:
    raise RuntimeError("current admitted executed pair is not applicable: " + gate)
record_path = ROOT / ".saipen/evidence/regression/regression-execution-35a2a41a76b34d03bd6aa3e4dcfe8ea2.json"
raw_record = record_path.read_bytes()
if hashlib.sha256(raw_record).hexdigest() != "81cc9a4f24c513bd2b7402981b9a58fe23added230d4c915bbed11142d43fb2d":
    raise RuntimeError("admitted record bytes moved")
record = json.loads(raw_record)
contract = HERE / "regression-contract.json"
material = execution._load(ROOT, contract)
if material["verifier"] != record["verifier"]:
    raise RuntimeError("review runtime/environment/oracle differs from the admitted verifier")
baseline = tree_fingerprint(ROOT)
canonical = {name: hashlib.sha256((ROOT / ".saipen" / name).read_bytes()).hexdigest()
             for name in ("STATE.md", "BOARD.md", "LOG.md")}
runs = [execution._measure(material, "before", material["prior"]),
        execution._measure(material, "after", material["current"])]
if ([item["exit_code"] for item in runs] != [1, 0]
        or [item["ran"] for item in runs] != [13, 13]
        or runs[0]["failed"] != 17 or runs[1]["failed"] != 0
        or any(item["skipped"] for item in runs)):
    raise RuntimeError("independent remeasurement contradicts the genuine pair")
if tree_fingerprint(ROOT) != baseline:
    raise RuntimeError("review changed the live source generation")
if canonical != {name: hashlib.sha256((ROOT / ".saipen" / name).read_bytes()).hexdigest()
                 for name in canonical}:
    raise RuntimeError("review changed canonical memory")
value = {"ok": True, "work": "T-1714", "phase": "REVIEW", "verifier": material["verifier"],
         "runtime": material["runtime"], "fingerprint": baseline, "runs": runs,
         "admitted_record": str(record_path.relative_to(ROOT)),
         "admitted_record_sha256": hashlib.sha256(raw_record).hexdigest(),
         "canonical_unchanged": True, "source_unchanged": True,
         "limits": "Independent read-only reexecution using the same admitted input contract/record. "
                   "Repository measurement helper owns child cleanup; no new authoritative receipt/profile/event."}
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"ok": True, "phase": "REVIEW", "verifier": material["verifier"],
                  "runs": [{key: item[key] for key in ("stage", "exit_code", "ran", "failed", "skipped")}
                           for item in runs], "record": str(output)}))
