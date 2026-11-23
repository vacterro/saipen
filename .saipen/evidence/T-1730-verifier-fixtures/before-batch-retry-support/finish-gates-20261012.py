"""Adopt one live verification runner, then run the remaining fixed gates.

This local test job changes no protocol, ownership, oracle or lifecycle state.
It never restarts a missing run or fabricates a cache or acceptance receipt.
"""

import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

directory = Path(__file__).resolve().parent
root = directory.parents[2]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.state import parse_state

status_path = directory / "gate-batch-current-01.json"
cancel_path = directory / "gate-batch-current-01.cancel"
if status_path.exists():
    raise SystemExit("Existing job evidence preserved; do not start a second batch.")
status = {"job_pid": os.getpid(), "status": "waiting", "runner_pid": int(sys.argv[1]),
          "started_utc": datetime.now(timezone.utc).isoformat(), "completed": []}


def save(**updates):
    status.update(updates)
    staging = status_path.with_suffix(".tmp")
    staging.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, status_path)
    print(json.dumps(status), flush=True)


def check_boundary():
    if cancel_path.exists():
        raise RuntimeError("local gate batch cancelled")
    state = parse_state((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
    if state.get("phase") != "VERIFY" or state.get("task") != "T-1730":
        raise RuntimeError("the original VERIFY T-1730 execution boundary changed")
    check = subprocess.run([sys.executable, "-B", str(directory / "check-subject.py")],
                           cwd=root, capture_output=True, text=True, encoding="utf-8", check=True)
    if not json.loads(check.stdout)["unchanged"]:
        raise RuntimeError("the verified source inventory changed")


try:
    check_boundary()
    save()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00101000, False, status["runner_pid"])
    if handle:
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *[ctypes.byref(value) for value in times]):
                raise RuntimeError("runner creation time cannot be verified")
            ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            created = ticks / 10_000_000 - 11_644_473_600
            expected = datetime.fromisoformat(sys.argv[2]).timestamp()
            if abs(created - expected) > 0.01:
                raise RuntimeError("runner PID belongs to another process generation")
            while True:
                result = kernel.WaitForSingleObject(handle, 30000)
                if result == 0:
                    break
                if result != 258:
                    raise RuntimeError("native runner observation failed")
                if cancel_path.exists():
                    raise RuntimeError("local gate batch cancelled")
        finally:
            kernel.CloseHandle(handle)
    core_result = json.loads((directory / "core-unit-current-01-result.json").read_text("utf-8"))
    core_verdict = json.loads((directory / "core-unit-current-01.txt").read_text("utf-8"))
    if core_result["exit_code"] or not core_verdict.get("ok") or core_verdict["verdict"] != "PASS":
        raise RuntimeError("the adopted whole family did not complete PASS")
    if not core_verdict.get("ran") or core_verdict.get("red") or core_verdict.get("problems"):
        raise RuntimeError("the adopted whole family has missing tests or unresolved failures")
    save(status="running", core_record=core_verdict["record"])
    for label, script in (
        ("floor-current-01", "tools/audit_floor.py"),
        ("order-current-01", "tools/audit_order.py"),
        ("tags-current-01", "tools/audit_tags.py"),
        ("audit-current-01", "tools/audit_checks.py"),
        ("scenarios-current-01", "tools/run_scenarios.py"),
        ("parity-current-01", "tools/audit_parity.py"),
    ):
        check_boundary()
        save(current_gate=label)
        command = [sys.executable, "-B", str(directory / "run-gate-20261012.py"),
                   label, "{python}", "-B", script]
        # CMD supplies the same native verification environment already proved
        # for this Work; fixed argv is quoted by the Windows argv serializer.
        result = subprocess.run([os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
                                 "/d", "/c", subprocess.list2cmdline(command)], cwd=root)
        if result.returncode:
            raise RuntimeError(f"mandatory gate {label} returned {result.returncode}")
        status["completed"].append(label)
        save()
    check_boundary()
    save(status="completed", current_gate=None,
         finished_utc=datetime.now(timezone.utc).isoformat())
except Exception as error:
    save(status="stopped", reason=f"{type(error).__name__}: {error}",
         finished_utc=datetime.now(timezone.utc).isoformat())
    raise SystemExit(1)
