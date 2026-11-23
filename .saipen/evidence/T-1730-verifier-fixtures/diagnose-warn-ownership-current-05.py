"""Capture the real warn-ownership control without changing its verdict."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

directory = Path(__file__).resolve().parent
root = directory.parents[2]
record_path = directory / "diagnose-warn-ownership-current-05.json"
if record_path.exists():
    raise SystemExit("Existing diagnostic evidence preserved.")
sys.path.insert(0, str(root / "tools"))
import audit_checks as audit

record = {"pid": os.getpid(), "commands": [], "validator_calls": []}
original_run = subprocess.run


def native(label, *args):
    result = original_run(
        [os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
         "/d", "/c", "bin\\saipen.cmd", *args, "--json"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    output = directory / f"{label}-current-05.txt"
    output.write_text(result.stdout + result.stderr, encoding="utf-8")
    record["commands"].append({"label": label, "exit_code": result.returncode,
                               "output": output.name})
    if result.returncode:
        raise RuntimeError(f"native {label} refused; preserved {output.name}")
    return json.loads(result.stdout)


def recorded_run(command, **kwargs):
    started = time.monotonic()
    result = original_run(command, **kwargs)
    if any(str(part).replace("\\", "/").endswith("/tools/validate.py")
           for part in command):
        label = f"warn-validator-{len(record['validator_calls']) + 1:02d}-current-05"
        (directory / (label + ".txt")).write_text(
            result.stdout + result.stderr, encoding="utf-8")
        record["validator_calls"].append({
            "command": [str(part) for part in command], "exit_code": result.returncode,
            "elapsed_s": round(time.monotonic() - started, 3), "output": label + ".txt",
        })
    return result


try:
    refreshed = native("T1695-warn-reverify", "work", "reverify", "T-1695", "--contract",
                       ".saipen/evidence/T-1726-closed-contracts/T1695-focused-contract.json")
    if (refreshed.get("closed_contract") or {}).get("status") != "CURRENT_PASS":
        raise RuntimeError("fresh actual execution did not establish focused CURRENT_PASS")
    current = native("T1695-warn-currentness", "work", "contracts", "T-1695", "--limit", "3")
    if current.get("counts") != {"CURRENT_PASS": 1}:
        raise RuntimeError("same-environment focused currentness did not hold")
    with tempfile.TemporaryDirectory(prefix="saipen-warn-native-control-") as temporary:
        context = audit.ProbeContext(Path(temporary), [], None)
        error = audit.build_pristine(context)
        if error:
            raise RuntimeError(error)
        subprocess.run = recorded_run
        try:
            record["problem"] = audit.warn_ownership_probe(context.pristine, Path(temporary))
        finally:
            subprocess.run = original_run
    record["status"] = "observed"
except Exception as error:
    record["status"] = "unavailable"
    record["reason"] = f"{type(error).__name__}: {error}"
finally:
    subprocess.run = original_run
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2), flush=True)
