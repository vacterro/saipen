"""Run the identical frozen regression against the old and proposed owners."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
location = json.loads((evidence / "location.json").read_text(encoding="utf-8"))
subject = Path(location["subject"])
owners = (
    "tools/saipen_engine/state.py",
    "tools/saipen_engine/audit_route.py",
    "tools/saipen_engine/router.py",
    "tools/saipen_engine/operations.py",
    "tools/validate.py",
)
frozen = ("tools/test_t1704_goal_checkpoint_priority.py", "tests/fixtures/t1703-valve-audit.json")
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
test_before = {name: digest(subject / name) for name in frozen}
proposed = {name: (subject / name).read_bytes() for name in owners}
try:
    for name in owners:
        (subject / name).write_bytes((root / name).read_bytes())
    red = subprocess.run(
        [sys.executable, str(evidence / "run.py"), "red-frozen",
         "tools.test_t1704_goal_checkpoint_priority"], cwd=root,
    ).returncode
finally:
    for name, content in proposed.items():
        (subject / name).write_bytes(content)
test_after = {name: digest(subject / name) for name in frozen}
assert test_before == test_after, "regression oracle changed during pair"
assert red == 1, f"expected pre-fix failures, got {red}"
green = subprocess.run(
    [sys.executable, str(evidence / "run.py"), "green-frozen",
     "tools.test_t1704_goal_checkpoint_priority", "tools.test_t1494_continuation_authority",
     "tools.test_t1293_valve_resume_audit_route", "tools.test_audit_route",
     "tools.test_reconcile_valve", "tools.test_command_routing", "tools.test_t1619_iteration_boundary"],
    cwd=root,
).returncode
pair = {"red_exit": red, "green_exit": green, "oracle_sha256": test_after,
        "live_code_applied": False, "live_authority_granted": False}
(evidence / "pair.json").write_text(json.dumps(pair, indent=2) + "\n", encoding="utf-8")
print(json.dumps(pair, indent=2))
raise SystemExit(green)
