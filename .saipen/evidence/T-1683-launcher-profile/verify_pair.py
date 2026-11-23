"""Exact pre-task injector bytes against the final unchanged shell oracle."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
paths = ("bootstrap/inject.sh", "bootstrap/inject.ps1")
before = {path: (EVIDENCE / "pre" / path).read_bytes() for path in paths}
after = {path: (ROOT / path).read_bytes() for path in paths}
test = ROOT / "tools" / "test_t1683_launcher_profile.py"
environment = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
environment.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
command = [sys.executable, "-B", "-m", "unittest", "test_t1683_launcher_profile"]

def subject_digest(blobs):
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.encode() + b"\0" + blobs[path])
    return digest.hexdigest()[:16]

def run(label):
    process = subprocess.run(
        command, cwd=ROOT / "tools", env=environment,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=120,
    )
    (EVIDENCE / (label + ".out.txt")).write_bytes(process.stdout + process.stderr)
    return process.returncode

try:
    for path, blob in before.items():
        (ROOT / path).write_bytes(blob)
    pre_rc = run("red")
finally:
    for path, blob in after.items():
        (ROOT / path).write_bytes(blob)
post_rc = run("green")
control_rc = run("control")
pair = {
    "verifier": hashlib.sha256(test.read_bytes()).hexdigest()[:16],
    "pre_subject": subject_digest(before), "post_subject": subject_digest(after),
    "pre_rc": pre_rc, "post_rc": post_rc, "control_rc": control_rc,
    "held": pre_rc != 0 and post_rc == 0 and control_rc == 0,
    "command": "python -B -m unittest test_t1683_launcher_profile",
}
(EVIDENCE / "pair.json").write_text(json.dumps(pair, indent=2) + "\n", encoding="utf-8")
print(json.dumps(pair))
sys.exit(0 if pair["held"] else 1)
