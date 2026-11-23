"""Hold one oracle against the exact inherited and drafted CLI bytes."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
PROJECT = Path(json.loads((EVIDENCE / "scratch.json").read_text())["project"])
SUBJECT = PROJECT / "tools" / "saipen.py"
TEST = PROJECT / "tools" / "test_t1631_argv_values.py"
after = SUBJECT.read_bytes()
baseline = EVIDENCE / "pre" / "tools" / "saipen.py"
baseline.parent.mkdir(parents=True, exist_ok=True)
if baseline.is_file():
    before = baseline.read_bytes()
else:
    before = (ROOT / "tools" / "saipen.py").read_bytes()
    baseline.write_bytes(before)
environment = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
environment.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
command = [sys.executable, "-B", "-m", "unittest", "test_t1631_argv_values"]

def run(label):
    process = subprocess.run(
        command, cwd=PROJECT / "tools", env=environment,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=120,
    )
    (EVIDENCE / (label + ".out.txt")).write_bytes(process.stdout + process.stderr)
    return process.returncode

try:
    SUBJECT.write_bytes(before)
    pre_rc = run("red")
finally:
    SUBJECT.write_bytes(after)
post_rc = run("green")
control_rc = run("control")
verifier = hashlib.sha256(TEST.read_bytes()).hexdigest()[:16]
pair = {
    "verifier": verifier,
    "pre_subject": hashlib.sha256(before).hexdigest()[:16],
    "post_subject": hashlib.sha256(after).hexdigest()[:16],
    "pre_rc": pre_rc, "post_rc": post_rc, "control_rc": control_rc,
    "held": pre_rc != 0 and post_rc == 0 and control_rc == 0,
    "command": "python -B -m unittest test_t1631_argv_values",
}
(EVIDENCE / "pair.json").write_text(json.dumps(pair, indent=2) + "\n", encoding="utf-8")
print(json.dumps(pair))
sys.exit(0 if pair["held"] else 1)
