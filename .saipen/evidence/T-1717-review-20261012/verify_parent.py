"""Verify the completed investigation and the canonical source closure boundary."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import intake, operations

label = sys.argv[1]
output = HERE / (label + "-parent.json")
if output.exists():
    raise RuntimeError("immutable parent evidence already exists")
docs, state, board, _ = operations._read(ROOT)
assert state["task"] == "T-1717" and state["phase"] == label.upper()
assert board["tickets"]["T-1717"]["fields"]["owner"] == "saipen-cli"
assert all(board["tickets"][work]["section"] == "## DONE" for work in ("T-1718", "T-1721"))
integrity = intake.verify_integrity(ROOT, "SRC-216")
coverage = intake.coverage_summary(ROOT, "SRC-216")
gate = intake.work_closure_gate(ROOT, "T-1717")
assert integrity["ok"] and gate["ok"] and coverage["terminal"] == coverage["actionable"] == 10
for name in ("original-evidence.json", "receipt-evidence-corrected.json", "consumer-protocol.json",
             "FINAL-INVESTIGATION.md"):
    assert (HERE / name).is_file()
original = json.loads((HERE / "original-evidence.json").read_text())
search = json.loads((HERE / "receipt-evidence-corrected.json").read_text())
consumer = json.loads((HERE / "consumer-protocol.json").read_text())
assert original["consumer_unchanged_during_probe"]
assert search["known_good_hash_matching_passed"] and not search["exact_digest_matches"]
assert consumer["canonical_unchanged"] and consumer["history_unchanged"]
assert consumer["exit_code"] == 1 and all(consumer["absence"].values())

def authority_hashes():
    names = ["BOARD.md", "STATE.md", "LOG.md", "IDENTITY.md", "intake/index.json",
             "intake/active/SRC-216.md", "intake/active/SRC-216.meta.json",
             "intake/contracts/SRC-216.json", "intake/coverage/SRC-216.json"]
    return {name: hashlib.sha256((ROOT / ".saipen" / name).read_bytes()).hexdigest()
            for name in names}

before = authority_hashes()
control = subprocess.run([str(ROOT / "bin/saipen.cmd"), "--json", "source", "close", "SRC-216"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
refusal = json.loads(control.stdout)
assert control.returncode != 0 and not refusal["ok"] and refusal["code"] == "SOURCE_WORK_ACTIVE"
assert "T-1717" in json.dumps(refusal), refusal
assert authority_hashes() == before
result = {"phase": state["phase"], "work": state["task"], "gate": gate,
          "coverage": coverage, "source_integrity": integrity,
          "completed_children": ["T-1718", "T-1721"],
          "premature_source_closure_refused": refusal,
          "canonical_unchanged": True,
          "consumer_verdict": "FAIL: 4 problems/57 warnings; original detail absent and LIVE outcome unproved",
          "source_ready_after_work_done": True, "source_closed": False}
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"phase": state["phase"], "investigation_verified": True,
                  "source_clauses": 10, "completed_children": 2,
                  "premature_close_control": "REFUSED_WITH_ZERO_WRITES",
                  "foreign_product_acceptance": "NOT_CLAIMED"}))
