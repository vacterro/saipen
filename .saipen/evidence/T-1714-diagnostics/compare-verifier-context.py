"""Measure native-versus-launcher context without disclosing values."""
import json
import os
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.process_tree import run

environment = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
environment.update(SAIPEN_CAPABILITY="no-publish", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
results = []
for command in ([sys.executable, "-B", str(here / "probe-verifier-context.py")],
                [str(here / "probe-verifier-context.cmd")]):
    completed = run(command, cwd=root, env=environment, capture_output=True, timeout=45)
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace"))
    results.append(json.loads(completed.stdout))
left, right = results
different = sorted(key for key in left["environment"].keys() | right["environment"].keys()
                   if left["environment"].get(key) != right["environment"].get(key))
value = {"native": {key: item for key, item in left.items() if key != "environment"},
         "launcher": {key: item for key, item in right.items() if key != "environment"},
         "different_environment_keys": different,
         "limits": "Only environment value hashes were compared in memory; no secret values saved or printed."}
output = here / "verifier-context-comparison.json"
if output.exists():
    raise RuntimeError("comparison already exists")
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps(value))
