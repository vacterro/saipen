"""Run the same repository oracle/configuration against one selected subject."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

root, label = Path(sys.argv[1]).resolve(), sys.argv[2]
evidence = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "tools"))
from saipen_engine import core_unit  # noqa: E402
from test_hermetic_env import hermetic_env  # noqa: E402

command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tools",
           "-p", "test_t1687_identity_diagnostics.py", "-v"]
config = {"command": command, "timeout_s": 120, "encoding": "utf-8",
          "hermetic_helper_sha256": hashlib.sha256(
              (root / "tools" / "test_hermetic_env.py").read_bytes()).hexdigest()}
oracle = (root / "tools" / "test_t1687_identity_diagnostics.py").read_bytes()
verifier = hashlib.sha256(oracle + json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]
subject = core_unit.tree_fingerprint(root)
run = subprocess.run(command, cwd=root, env=hermetic_env(PYTHONUTF8="1"),
                     capture_output=True, encoding="utf-8", timeout=120)
for stream in ("stdout", "stderr"):
    (evidence / f"{label}.{stream}.txt").write_text(getattr(run, stream), encoding="utf-8")
count = re.search(r"^Ran (\d+) tests? in", run.stderr, re.MULTILINE)
record = {"root": str(root), "verifier": verifier, "subject": subject,
          "configuration": config, "ran": int(count[1]) if count else None,
          "exit_code": run.returncode}
(evidence / f"{label}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
print(run.stderr)
raise SystemExit(run.returncode if count and int(count[1]) == 3 else 2)
