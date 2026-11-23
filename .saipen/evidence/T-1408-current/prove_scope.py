"""Read-only proof of the already-completed SRC-070 local commit scope."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMMIT = "376d7c7806dca4442b25b156415a051daa75906f"
PATHS = ["saipen/IMPROVE.md", "saipen/REGISTRY.json", "tools/improve.py",
         "tools/run_scenarios.py", "tools/saipen.py"]
def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)
files = git("diff-tree", "--no-commit-id", "--name-only", "-r", COMMIT).decode().splitlines()
assert sorted(files) == sorted(PATHS), files
subprocess.run(["git", "merge-base", "--is-ancestor", COMMIT, "HEAD"], cwd=ROOT, check=True)
cli_patch = git("show", "--format=", COMMIT, "--", "tools/saipen.py")
assert b"quarantine" not in cli_patch and b"SOURCE_" not in cli_patch, cli_patch
later = git("rev-parse", "2eecc65c").decode().strip()
subprocess.run(["git", "merge-base", "--is-ancestor", COMMIT, later], cwd=ROOT, check=True)
subprocess.run(["git", "merge-base", "--is-ancestor", later, "HEAD"], cwd=ROOT, check=True)
result = {"source": "SRC-070", "commit": COMMIT, "paths": files,
          "commit_is_ancestor": True, "foreign_quarantine_hunks_in_cli": False,
          "later_T1400_commit": later, "later_T1400_is_ancestor": True,
          "head": git("rev-parse", "HEAD").decode().strip(),
          "current_hashes": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                             for path in PATHS},
          "proof_limits": ["Local Git ancestry is not remote push or release publication evidence.",
                           "Historical receipt witness remains model_supplied; not upgraded.",
                           "Current mandatory scenario gate failed and must be repaired before acceptance."]}
target = Path(__file__).with_name("scope.json")
target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
