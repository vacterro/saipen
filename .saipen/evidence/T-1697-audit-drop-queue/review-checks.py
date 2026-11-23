"""Independent REVIEW execution of canonical and affected-neighbor checks."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
CHECKS = [
    ("focused", [sys.executable, "-m", "unittest", "tools.test_audit_inbox",
                 "tools.test_audit_enqueue", "tools.test_audit_manifest",
                 "tools.test_automation_block", "tools.test_next_action_deadlock",
                 "tools.test_protocol_registry", "tools.test_response_surface_contract.BudgetTests"]),
    ("ruff", [sys.executable, "-m", "ruff", "check", "tools/", "tests/"]),
    ("whitespace", ["git", "-c", "core.safecrlf=false", "diff", "--check"]),
    ("core", [sys.executable, "tools/validate.py", "--gate", "core"]),
]
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


def run(spec):
    name, command = spec
    result = subprocess.run(command, cwd=ROOT, env=ENV, capture_output=True, timeout=300)
    output = OUT / ("review-" + name + ".txt")
    output.write_bytes(result.stdout + result.stderr)
    record = {"name": name, "command": command, "exit_code": result.returncode,
              "output": output.name, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    print(json.dumps(record), flush=True)
    return record


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    records = list(executor.map(run, CHECKS))
(OUT / "review-checks.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
assert all(record["exit_code"] == 0 for record in records), records
