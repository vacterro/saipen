"""Read-only diagnosis of the real post-cap validator conflict; no fix or waiver."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.audit_inbox import projection
from saipen_engine.audit_route import route_violation
from saipen_engine.board import parse_board

before = {name: (ROOT / ".saipen" / name).read_bytes()
          for name in ("STATE.md", "BOARD.md", "LOG.md")}
process = subprocess.run([str(ROOT / "bin/saipen.cmd"), "status", "--json"], cwd=ROOT,
                         capture_output=True, timeout=90)
assert process.returncode == 0
status = json.loads(process.stdout)
assert status["automation"]["disposition"] == "WAIT_USER"
assert status["conformance_status"]["status"] == "CURRENT_FAIL"
(OUT / "cap-current-status.json").write_bytes(process.stdout)
board = parse_board(before["BOARD.md"].decode("utf-8"))
assert not board["errors"]
tickets = board["tickets"]
doing = [name for name, row in tickets.items() if row["section"] == "## DOING"]
assert status["task"] in doing
pending = projection(ROOT)
categories = json.loads((ROOT / "saipen/REGISTRY.json").read_bytes())["wait_categories"]
args = {"tickets": tickets, "agent": "saipen-cli"}
actual = route_violation(pending, status["next_action"], doing, categories, **args)
phase_control = route_violation(pending, "PHASE REVIEW " + status["task"], doing, categories, **args)
scope_control = route_violation(pending, "WAIT: scope selection -- choose an audit", doing, categories, **args)
assert actual, "the reported pure-check conflict did not reproduce"
assert phase_control is None and scope_control, "positive/negative instrument controls failed"
assert before == {name: (ROOT / ".saipen" / name).read_bytes() for name in before}
record = {"source_sha256": hashlib.sha256((ROOT / "tools/saipen_engine/audit_route.py").read_bytes()).hexdigest(),
          "actual_checkpoint": {"phase": status["phase"], "task": status["task"],
                                "next_action": status["next_action"], "doing": doing},
          "pending_projection": pending, "pure_check_actual_violation": actual,
          "phase_continuation_control": phase_control, "illegal_scope_wait_control": scope_control,
          "current_fail_receipt": status["conformance_status"]["receipt"]["receipt_id"],
          "canonical_bytes_unchanged": True, "code_change": False,
          "disposition": "Unadmitted follow-up defect; budget boundary preserved, not repaired or waived."}
(OUT / "cap-audit-conflict.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"conflict_reproduced": True, "positive_phase_control": "accepted",
                  "illegal_scope_control": "rejected", "canonical_bytes_unchanged": True,
                  "current_conformance": "CURRENT_FAIL", "code_change": False}))
