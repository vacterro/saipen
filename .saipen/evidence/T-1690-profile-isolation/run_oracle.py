"""Run the same disposable-profile oracle against one selected subject."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
label = sys.argv[2]
evidence = Path(__file__).resolve().parent
command = [sys.executable, "-B", "-m", "unittest", "test_t1690_profile_isolation", "-v"]
oracle = root / "tools" / "test_t1690_profile_isolation.py"
verifier = hashlib.sha256(oracle.read_bytes() + json.dumps(command).encode()).hexdigest()[:16]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.core_unit import tree_fingerprint
from test_hermetic_env import hermetic_env

subject = tree_fingerprint(root)
run = subprocess.run(
    command, cwd=root / "tools", env=hermetic_env(), stdin=subprocess.DEVNULL,
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
)
(evidence / f"{label}.stdout.txt").write_text(run.stdout, encoding="utf-8")
(evidence / f"{label}.stderr.txt").write_text(run.stderr, encoding="utf-8")
record = {"command": command, "root": str(root), "verifier": verifier,
          "subject": subject, "exit_code": run.returncode}
(evidence / f"{label}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
print(run.stderr[-6000:])
sys.exit(run.returncode)
