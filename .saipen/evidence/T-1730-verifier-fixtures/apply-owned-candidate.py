"""Apply the five owned files only if the live preimages still match."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
CANDIDATE = ROOT / ".saipen/evidence/T-1726-closed-contracts/cache-candidate/tools"
NAMES = ("run_scenarios.py", "audit_checks.py", "validate.py",
         "test_t1586_scenario_inputs.py", "test_t1581_phase_rename_knowledge.py")

for name in NAMES:
    live = ROOT / "tools" / name
    assert live.read_bytes() == (EVIDENCE / "before" / name).read_bytes(), (
        "live file changed after the owned preimage; preserve and reconcile", name)
for name in NAMES:
    raw = (CANDIDATE / name).read_bytes()
    (ROOT / "tools" / name).write_bytes(raw)
    print(name, hashlib.sha256(raw).hexdigest())
