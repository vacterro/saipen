"""Canonical checks with exact commands and bounded output references."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
prefix = sys.argv[1] if len(sys.argv) > 1 else "verify"
checks = [
    ("focused", [sys.executable, "-B", "-m", "unittest", "test_automation_block",
                 "test_response_surface_contract", "test_response_digest", "test_response_fact_binding",
                 "test_audit_inbox", "test_refusal_registry", "test_canonical_command_reachability",
                 "test_subprocess_utf8"], ROOT / "tools"),
    ("ruff", [sys.executable, "-m", "ruff", "check", "tools/", "tests/"], ROOT),
    ("whitespace", ["git", "-c", "core.safecrlf=false", "diff", "--check"], ROOT),
]


def run(spec):
    name, command, cwd = spec
    result = subprocess.run(command, cwd=cwd, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=300)
    output = result.stdout + result.stderr
    path = OUT / (prefix + "-" + name + ".out.txt")
    path.write_text(output, encoding="utf-8")
    record = {"check": name, "command": command, "cwd": str(cwd),
              "exit_code": result.returncode, "output": path.name,
              "output_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    print(json.dumps(record), flush=True)
    return record


with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    records = list(executor.map(run, checks))
(OUT / (prefix + "-checks.json")).write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
assert all(record["exit_code"] == 0 for record in records), records
