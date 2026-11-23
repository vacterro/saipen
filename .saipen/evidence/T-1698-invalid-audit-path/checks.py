"""Capture repeatable focused and canonical check output without hiding reds."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
LABEL = sys.argv[1]
CHECKS = [
    ("focused", [sys.executable, "-B", "-m", "unittest", "tools.test_audit_inbox",
                 "tools.test_audit_enqueue", "tools.test_audit_manifest",
                 "tools.test_automation_block", "tools.test_next_action_deadlock",
                 "tools.test_protocol_registry", "tools.test_response_surface_contract.BudgetTests",
                 "tools.test_refusal_registry", "tools.test_canonical_command_reachability",
                 "tools.test_subprocess_utf8"]),
    ("ruff", [sys.executable, "-B", "-m", "ruff", "check", "tools/", "tests/"]),
    ("whitespace", ["git", "-c", "core.safecrlf=false", "diff", "--check"]),
    ("core", [sys.executable, "-B", "tools/validate.py", "--gate", "core"]),
]
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


def run(spec):
    name, command = spec
    result = subprocess.run(command, cwd=ROOT, env=ENV, capture_output=True, timeout=360)
    output = OUT / f"{LABEL}-{name}.txt"
    output.write_bytes(result.stdout + result.stderr)
    record = {"name": name, "command": command, "exit_code": result.returncode,
              "output": output.name, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    print(json.dumps(record), flush=True)
    return record


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    records = list(executor.map(run, CHECKS))
(OUT / f"{LABEL}-checks.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
assert all(record["exit_code"] == 0 for record in records), records
