"""Hold the final native-module oracle against exact pre/post adapter bytes."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PROJECT = Path(json.loads((HERE / "scratch.json").read_text())["project"])
names = ["extensions/adapters/opencode/saipen-guard.js", "extensions/adapters/registry.json",
         "tools/saipen_engine/host_integration.py"]
before = {name: (HERE / "pre" / name).read_bytes() for name in names}
after = {name: (PROJECT / name).read_bytes() for name in names}
verifier = hashlib.sha256()
for name in ("tools/test_t1628_opencode_gap.py", "tools/test_guard_hostile_matrix.py"):
    verifier.update(name.encode())
    verifier.update((PROJECT / name).read_bytes())
environment = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
environment.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")

def run(label):
    result = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "test_t1628_opencode_gap"],
        cwd=PROJECT / "tools", env=environment, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=240,
    )
    (HERE / (label + ".out.txt")).write_bytes(result.stdout + result.stderr)
    return result.returncode

def identity(contents):
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update(contents[name])
    return digest.hexdigest()[:16]

try:
    for name in names:
        (PROJECT / name).write_bytes(before[name])
    pre_rc = run("red")
finally:
    for name in names:
        (PROJECT / name).write_bytes(after[name])
post_rc = run("green")
control_rc = run("control")
pair = {"verifier": verifier.hexdigest()[:16], "pre_subject": identity(before),
        "post_subject": identity(after), "pre_rc": pre_rc, "post_rc": post_rc,
        "control_rc": control_rc, "held": pre_rc != 0 and post_rc == control_rc == 0,
        "command": "python -B -m unittest test_t1628_opencode_gap"}
(HERE / "pair.json").write_text(json.dumps(pair, indent=2) + "\n", encoding="utf-8")
print(json.dumps(pair))
sys.exit(0 if pair["held"] else 1)
