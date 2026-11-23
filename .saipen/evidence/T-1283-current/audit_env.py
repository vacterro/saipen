"""Run the unchanged full audit with the live project's native Git path support."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
phase = sys.argv[1]
assert phase in ("VERIFY", "REVIEW")
run_id = sys.argv[2] if len(sys.argv) > 2 else ""
assert not run_id or re.fullmatch(r"[A-Za-z0-9-]{1,50}", run_id)
prefix = phase + "-audit-longpaths" + ("-" + run_id if run_id else "")
configured = subprocess.check_output(["git", "config", "--get", "core.longpaths"],
                                     cwd=ROOT, text=True, encoding="utf-8").strip()
assert configured == "true"
environment = dict(os.environ)
index = int(environment.get("GIT_CONFIG_COUNT", "0"))
environment["GIT_CONFIG_COUNT"] = str(index + 1)
environment[f"GIT_CONFIG_KEY_{index}"] = "core.longpaths"
environment[f"GIT_CONFIG_VALUE_{index}"] = configured
environment["PYTHONUNBUFFERED"] = "1"
command = [sys.executable, "-B", str(ROOT / "tools/audit_checks.py")]
output = HERE / (prefix + ".stdout")
error = HERE / (prefix + ".stderr")
with output.open("wb") as stdout, error.open("wb") as stderr:
    run = subprocess.run(command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, timeout=3600)
summary = next((line for line in reversed(output.read_bytes().decode("utf-8", errors="replace").splitlines())
                if line.startswith("AUDIT:")), "NO_COMPLETE_SUMMARY")
record = {"phase": phase, "command": command, "returncode": run.returncode,
          "timeout_seconds": 3600, "fixture_git_core_longpaths": configured,
          "global_git_configuration_changed": False, "cases_or_predicates_changed": False,
          "summary": summary, "stdout": output.name, "stderr": error.name}
(HERE / (prefix + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
raise SystemExit(run.returncode)
