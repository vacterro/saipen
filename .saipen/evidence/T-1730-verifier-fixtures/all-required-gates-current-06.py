"""Run unchanged mandatory gates sequentially on the final owned subject."""

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

target = directory / "all-required-gates-current-06.json"
if target.exists():
    raise SystemExit("Existing job evidence preserved.")
status = {"job_pid": os.getpid(), "status": "running", "completed": [],
          "started_utc": datetime.now(timezone.utc).isoformat()}


def save(**updates):
    status.update(updates)
    staging = target.with_suffix(".tmp")
    staging.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, target)
    print(json.dumps(status), flush=True)


def boundary():
    if (directory / "all-required-gates-current-06.cancel").exists():
        raise RuntimeError("local verification job cancelled")
    state = parse_state((root / ".saipen/STATE.md").read_text("utf-8"))
    if (state.get("phase"), state.get("task")) != ("VERIFY", "T-1730"):
        raise RuntimeError("the original VERIFY T-1730 boundary changed")
    subprocess.run([sys.executable, "-B", str(directory / "check-subject-current-06.py")],
                   cwd=root, capture_output=True, check=True)


def run(label, command):
    boundary()
    save(current_gate=label)
    result = subprocess.run([sys.executable, "-B", str(directory / "run-gate-20261012.py"),
                             label, *command], cwd=root)
    if result.returncode:
        raise RuntimeError(f"required verification {label} returned {result.returncode}")
    status["completed"].append(label)
    save()


try:
    boundary()
    save()
    prefix = [os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"), "/d", "/c"]
    run("T1695-current-06", [*prefix, "bin\\saipen.cmd", "work", "reverify", "T-1695",
        "--contract", ".saipen\\evidence\\T-1726-closed-contracts\\T1695-focused-contract.json", "--json"])
    fresh = json.loads((directory / "T1695-current-06.txt").read_text("utf-8"))
    if not fresh.get("ok") or (fresh.get("closed_contract") or {}).get("status") != "CURRENT_PASS":
        raise RuntimeError("actual native focused remeasurement did not establish CURRENT_PASS")
    run("T1695-currentness-06", [*prefix, "bin\\saipen.cmd", "work", "contracts", "T-1695",
                               "--limit", "3", "--json"])
    current = json.loads((directory / "T1695-currentness-06.txt").read_text("utf-8"))
    if current.get("counts") != {"CURRENT_PASS": 1}:
        raise RuntimeError("same-environment focused proof is not current")
    run("conformance-current-06", [*prefix, "bin\\saipen.cmd", "validate", "--json"])
    native = json.loads((directory / "conformance-current-06.txt").read_text("utf-8"))
    if not native.get("ok") or native.get("code") != "VALID":
        raise RuntimeError("native conformance did not return VALID")
    run("core-unit-current-06", ["--native-opencode", "{python}", "-B", "tools/core_unit.py",
                                "evidence", "T-1730", "--fresh"])
    for name, script in (("floor", "tools/audit_floor.py"), ("order", "tools/audit_order.py"),
                         ("tags", "tools/audit_tags.py"), ("audit", "tools/audit_checks.py"),
                         ("scenarios", "tools/run_scenarios.py"), ("parity", "tools/audit_parity.py")):
        run(f"{name}-current-06", ["{python}", "-B", script])
    boundary()
    save(status="completed", current_gate=None,
         finished_utc=datetime.now(timezone.utc).isoformat())
except Exception as error:
    save(status="stopped", reason=f"{type(error).__name__}: {error}",
         finished_utc=datetime.now(timezone.utc).isoformat())
    raise SystemExit(1)
