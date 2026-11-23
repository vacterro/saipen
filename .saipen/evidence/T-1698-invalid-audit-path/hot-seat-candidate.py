"""Recheck the preserved candidate without changing the gate's frozen tree."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
oracle = OUT / "regression.py"
verifier = hashlib.sha256(oracle.read_bytes()).hexdigest()
assert verifier == "8732220cbe13c4a8000201039e652c24fd462f8a67d142fc2410822969ed352d"
paths = [ROOT / "tools/saipen_engine/audit_inbox.py", ROOT / "tools/test_audit_inbox.py"]
before = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
records = []
for name, subject, expected in (
    ("pre", ROOT / "tools/saipen_engine/audit_inbox.py", 1),
    ("candidate", ROOT / ".saipen/kitchen/failed/T-1698/audit_inbox.py", 0),
):
    result = subprocess.run([sys.executable, "-B", str(oracle), str(subject)],
                            cwd=ROOT, capture_output=True, timeout=60)
    output = result.stdout + result.stderr
    (OUT / ("hot-seat-" + name + ".txt")).write_bytes(output)
    assert result.returncode == expected and b"Ran 4 tests" in output, output
    assert b"ERROR:" not in output, output
    assert (b"FAILED (failures=2)" if expected else b"\nOK") in output, output
    records.append({"subject": str(subject.relative_to(ROOT)), "exit_code": result.returncode,
                    "subject_sha256": hashlib.sha256(subject.read_bytes()).hexdigest(),
                    "output_sha256": hashlib.sha256(output).hexdigest()})
after = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
assert before == after
record = {"oracle_sha256": verifier, "runs": records, "frozen_owner_paths_unchanged": before == after,
          "limits": "candidate verification only; T-1698 remains BLOCKED, no source restoration or lifecycle claim"}
(OUT / "hot-seat-candidate.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
