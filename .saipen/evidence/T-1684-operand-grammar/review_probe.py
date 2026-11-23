"""REVIEW: independent real-CLI probe of the T-1684 verify clause.

Runs the live tools/saipen.py against a throwaway fixture project; never
touches this repository's .saipen/.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from test_guard_hostile_matrix import fresh_project  # noqa: E402

project = fresh_project()
env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
env["CLAUDE_CONFIG_DIR"] = ""


def cli(*args, extra_env=None):
    proc = subprocess.run(
        [sys.executable, "-B", str(ROOT / "tools/saipen.py"), "--project-root", str(project), *args],
        cwd=ROOT, env={**env, **(extra_env or {})}, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    return proc.returncode, proc.stdout, proc.stderr


board = project / ".saipen/BOARD.md"
results = {}

rc, out, _ = cli("--json", "ticket", "add", "P3", "Probe help literal", "--verify", "--help")
results["verify_help_literal_write"] = (rc, json.loads(out).get("code"), "verify: --help" in board.read_text(encoding="utf-8"))

rc, out, _ = cli("--json", "ticket", "add", "P3", "Probe plus literal", "--verify", "+")
results["verify_plus_literal_write"] = (rc, json.loads(out).get("code"), "verify: +" in board.read_text(encoding="utf-8"))

rc, out, _ = cli("--json", "ticket", "add", "P3", "Probe dash literal", "--verify", "--")
results["verify_dashdash_literal_write"] = (rc, json.loads(out).get("code"), "Probe dash literal | verify: --\n" in board.read_text(encoding="utf-8"))

before = board.read_bytes()
rc, out, _ = cli("--json", "ticket", "add", "P3", "Probe readonly", "--verify", "--help",
                 extra_env={"SAIPEN_CAPABILITY": "read-only"})
results["readonly_inverse"] = (rc, json.loads(out).get("code"), board.read_bytes() == before)

rc, out, _ = cli("ticket", "--help")
results["real_help"] = (rc, out.lstrip().startswith("usage:"), board.read_bytes() == before)

rc, out, _ = cli("host", "entry", "--host", "--", "--", "status")
results["host_entry_boundary"] = (rc, "phase:" in out)

rc, out, _ = cli("--json", "status", "+", "status")
results["real_compound"] = (rc, out.count('"phase"') >= 1)

print(json.dumps(results, indent=1))
expected = {
    "verify_help_literal_write": [0, "TICKET_ADDED", True],
    "verify_plus_literal_write": [0, "TICKET_ADDED", True],
    "verify_dashdash_literal_write": [0, "TICKET_ADDED", True],
    "readonly_inverse": [1, "CAPABILITY_DENIED", True],
}
bad = {k: v for k, v in expected.items() if list(results[k]) != v}
bad.update({k: results[k] for k in ("real_help",) if results[k] != (0, True, True)})
if results["host_entry_boundary"] != (0, True):
    bad["host_entry_boundary"] = results["host_entry_boundary"]
if results["real_compound"][0] != 0:
    bad["real_compound"] = results["real_compound"]
print("REVIEW-PROBE", "FAIL" if bad else "PASS", json.dumps(bad))
sys.exit(1 if bad else 0)
