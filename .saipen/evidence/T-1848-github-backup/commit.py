"""Create the isolated backup commit with the repository's normal hooks."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys

folder = Path(__file__).resolve().parent
root = folder.parents[2]
plan = json.loads((folder / "prepared.json").read_text(encoding="utf-8"))
env = os.environ.copy()
for key in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
    env.pop(key, None)
env["GIT_OPTIONAL_LOCKS"] = "0"
env["GIT_TERMINAL_PROMPT"] = "0"
commit_args = ["--amend", "--no-edit"] if "--amend" in sys.argv else ["-F", str(folder / "commit-message.txt")]
command = ["git", "--git-dir", plan["auxiliary_git_dir"], "commit", *commit_args]
completed = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=300)
output = completed.stdout + completed.stderr
(folder / "normal-commit.log").write_bytes(output)
clean = re.sub(r"\x1b\[[0-9;]*m", "", output.decode("utf-8", errors="replace"))
failures = [line.strip() for line in clean.splitlines()
            if line.startswith("FAIL:") or "Validation FAILED:" in line
            or "VALIDATION MUTATED THE TREE" in line]
head = subprocess.run(["git", "--git-dir", plan["auxiliary_git_dir"], "rev-parse", "HEAD"],
                      cwd=root, env=env, capture_output=True, check=True).stdout.decode().strip()
result = {"exit_code": completed.returncode, "commit": head, "branch": plan["branch"],
          "mandatory_failure_lines": failures,
          "canonical_pass": "Validation complete. Agent is conformant." in clean,
          "portable_floor_pass": "Portable floor complete: no structural break found." in clean,
          "pushed": False}
(folder / "commit-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
if completed.returncode or failures or not result["canonical_pass"] or not result["portable_floor_pass"]:
    raise SystemExit(1)
