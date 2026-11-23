"""Refresh real environment-bound evidence and run only outstanding gates.

Every child uses the same unchanged inherited environment and native CMD
transport. No historical receipt, verifier, environment value or oracle is
rewritten. This local job does not close Work or change its phase.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

directory = Path(__file__).resolve().parent
root = directory.parents[2]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.state import parse_state

status_path = directory / "remaining-gates-current-03.json"
cancel = directory / "remaining-gates-current-03.cancel"
if status_path.exists():
    raise SystemExit("Existing job evidence preserved; do not start another copy.")
status = {"job_pid": os.getpid(), "status": "running", "completed": [],
          "started_utc": datetime.now(timezone.utc).isoformat()}


def save(**updates):
    status.update(updates)
    staging = status_path.with_suffix(".tmp")
    staging.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, status_path)
    print(json.dumps(status), flush=True)


def boundary():
    if cancel.exists():
        raise RuntimeError("local verification job cancelled")
    state = parse_state((root / ".saipen/STATE.md").read_text("utf-8"))
    if (state.get("phase"), state.get("task")) != ("VERIFY", "T-1730"):
        raise RuntimeError("the original VERIFY T-1730 boundary changed")
    checked = subprocess.run([sys.executable, "-B", str(directory / "check-subject.py")],
                             cwd=root, capture_output=True, text=True, encoding="utf-8", check=True)
    if not json.loads(checked.stdout)["unchanged"]:
        raise RuntimeError("the implementation inventory changed")


def run(label, command):
    boundary()
    save(current_gate=label)
    args = [sys.executable, "-B", str(directory / "run-gate-20261012.py"), label, *command]
    result = subprocess.run([os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
                             "/d", "/c", subprocess.list2cmdline(args)], cwd=root)
    if result.returncode:
        raise RuntimeError(f"required verification {label} returned {result.returncode}")
    status["completed"].append(label)
    save()


try:
    boundary()
    save()
    transport = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
    prefix = [transport, "/d", "/c"]
    run("T1695-current-03", [*prefix, "bin\\saipen.cmd work reverify T-1695 --contract "
                             ".saipen\\evidence\\T-1726-closed-contracts\\T1695-focused-contract.json --json"])
    verified = json.loads((directory / "T1695-current-03.txt").read_text("utf-8"))
    focused = verified.get("closed_contract") or {}
    if not verified.get("ok") or focused.get("status") != "CURRENT_PASS" or not focused.get("executed"):
        raise RuntimeError("fresh native focused execution did not establish CURRENT_PASS")
    run("T1695-currentness-03", [*prefix, "bin\\saipen.cmd work contracts T-1695 --limit 3 --json"])
    current = json.loads((directory / "T1695-currentness-03.txt").read_text("utf-8"))
    if not current.get("ok") or current.get("counts") != {"CURRENT_PASS": 1}:
        raise RuntimeError("same-environment observation is not CURRENT_PASS")
    run("conformance-current-03", [*prefix, "bin\\saipen.cmd validate --json"])
    conformance = json.loads((directory / "conformance-current-03.txt").read_text("utf-8"))
    if not conformance.get("ok") or conformance.get("code") != "VALID":
        raise RuntimeError("native conformance did not return VALID")
    for name, script in (("audit", "tools/audit_checks.py"),
                         ("scenarios", "tools/run_scenarios.py"),
                         ("parity", "tools/audit_parity.py")):
        run(f"{name}-current-03", ["{python}", "-B", script])
    boundary()
    save(status="completed", current_gate=None,
         finished_utc=datetime.now(timezone.utc).isoformat())
except Exception as error:
    save(status="stopped", reason=f"{type(error).__name__}: {error}",
         finished_utc=datetime.now(timezone.utc).isoformat())
    raise SystemExit(1)
