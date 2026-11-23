"""Record isolated evidence canonically, then measure the live native gate."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
sys.path.insert(0, str(root / "tools"))
from saipen_engine import codec, state
from saipen_engine.core_unit import tree_fingerprint

location = json.loads((evidence / "location.json").read_text(encoding="utf-8"))
subject = Path(location["subject"])
prefix = [sys.executable, str(root / "tools/saipen.py")]

def run(label, argv, cwd=root):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="backslashreplace")
    try:
        stdout = json.loads(result.stdout)
    except ValueError:
        stdout = result.stdout
    record = {"argv": argv, "cwd": str(cwd), "exit_code": result.returncode,
              "stdout": stdout, "stderr": result.stderr}
    (evidence / f"{label}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": label, "exit_code": result.returncode,
                      "stdout": stdout, "stderr": result.stderr}, indent=2))
    return record

lint = run("lint-final", [sys.executable, "-m", "ruff", "check",
    "tools/saipen_engine/state.py", "tools/saipen_engine/audit_route.py",
    "tools/saipen_engine/router.py", "tools/saipen_engine/operations.py", "tools/validate.py",
    "tools/test_t1704_goal_checkpoint_priority.py"], cwd=subject)
assert lint["exit_code"] == 0, "draft lint failed"
before = state.parse_state(codec.read_doc(root / ".saipen/STATE.md"))
message = (
    "ISOLATED_DRAFT -- T-1704 parity patch only; identical 24-test oracle RED 12 exit 1, "
    "focused 184/0 GREEN exit 0; native fixtures pass, not live validation. "
    "Patch applicability/lint pass; no live code applied or authority granted. "
    "T-1703 REVIEW bounded 0/20 preserved; genuine host ingress unavailable. "
    "New audit/SAIPEN_20261010_1136.md retained unconsumed; no full-family run or DONE. "
    "Evidence: .saipen/evidence/T-1704-draft/REPORT.md"
)
checkpoint = run("checkpoint-final", [*prefix, "checkpoint", "RUN", "T-1704", message, "--json"])
after = state.parse_state(codec.read_doc(root / ".saipen/STATE.md"))
preserved = ("task", "phase", "transition_from", "next_action", "blocker", "agent",
             "execution_intent", "goal_waves", "goal_tickets")
assert all(before.get(key) == after.get(key) for key in preserved), "execution position changed"
validation = run("native-final", [*prefix, "validate", "--json"])
report = {"preserved": {key: after.get(key) for key in preserved},
          "before_event": before.get("last_event"), "after_event": after.get("last_event"),
          "checkpoint_exit": checkpoint["exit_code"], "native_exit": validation["exit_code"],
          "live_source_fingerprint": tree_fingerprint(root),
          "live_canonical_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                    for name in location["canonical_sha256"]},
          "authority_tuple_present": any(key in after for key in
                                         ("continuation_authority", "authority_source",
                                          "authority_until", "safety_valve_mode")),
          "code_applied_to_live_root": False}
(evidence / "position-final.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
