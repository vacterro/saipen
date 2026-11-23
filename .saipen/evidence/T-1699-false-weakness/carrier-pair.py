"""A fresh red/green pair for the broken input carrier, not for engine code."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
prefix = sys.argv[1]
oracle = OUT / "carrier-oracle.py"
records = []
for name, subject, expected in (("pre", ROOT / ".saipen/evidence/T-1696-queued-audapack/guardrails.py", 1),
                                 ("post", OUT / "guardrails-fixed.py", 0)):
    result = subprocess.run([sys.executable, "-B", str(oracle), str(subject)], cwd=ROOT,
                            capture_output=True, timeout=180)
    raw = result.stdout + result.stderr
    (OUT / (prefix + "-carrier-" + name + ".txt")).write_bytes(raw)
    assert result.returncode == expected and b"Ran 4 tests" in raw and b"ERROR:" not in raw, raw
    assert (b"FAILED (failures=2)" if expected else b"\nOK") in raw, raw
    records.append({"label": name, "verifier_sha256": hashlib.sha256(oracle.read_bytes()).hexdigest(),
                    "subject_sha256": hashlib.sha256(subject.read_bytes()).hexdigest(),
                    "exit_code": result.returncode, "output_sha256": hashlib.sha256(raw).hexdigest()})
assert records[0]["verifier_sha256"] == records[1]["verifier_sha256"]
(OUT / (prefix + "-carrier-pair.json")).write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
print(json.dumps(records))
