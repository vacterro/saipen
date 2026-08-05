#!/usr/bin/env python3
"""Register or remove the saipen-autoinject Windows Scheduled Task.

The task invokes tools/autoinject.py --quiet-when-fresh every 15 minutes,
indefinitely, with no console window (pythonw) and no output unless the
installed copies are stale.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "saipen-autoinject"
HERE = Path(__file__).resolve().parent
PYTHONW = Path(sys.executable).with_name("pythonw.exe")
SCRIPT = HERE / "autoinject.py"


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    return r.returncode, (r.stdout + r.stderr).strip()


def task_exists() -> bool:
    rc, _ = _run(["schtasks", "/query", "/tn", TASK_NAME])
    return rc == 0


def create() -> int:
    tr = f'"{PYTHONW}" "{SCRIPT}" --quiet-when-fresh'
    rc, out = _run(["schtasks", "/create", "/tn", TASK_NAME, "/tr", tr,
                    "/sc", "MINUTE", "/mo", "15", "/f"])
    print(out or (f"task {TASK_NAME} created" if rc == 0 else "create failed"))
    return 0 if rc == 0 else 1


def remove() -> int:
    if not task_exists():
        print(f"task {TASK_NAME} not present")
        return 0
    rc, out = _run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"])
    print(out or (f"task {TASK_NAME} removed" if rc == 0 else "remove failed"))
    return 0 if rc == 0 else 1


def status() -> int:
    rc, out = _run(["schtasks", "/query", "/tn", TASK_NAME, "/v", "/fo", "LIST"])
    if rc != 0:
        print(f"task {TASK_NAME} not registered")
        return 1
    keep = ("TaskName", "Status", "Schedule Type", "Start Time", "Repeat",
            "Last Run Time", "Last Result", "Task To Run")
    for ln in out.splitlines():
        if any(k in ln for k in keep):
            print(ln)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", nargs="?", default="create",
                    choices=("create", "remove", "status"),
                    help="what to do (default: create)")
    args = ap.parse_args(argv)
    return {"create": create, "remove": remove, "status": status}[args.action]()


if __name__ == "__main__":
    sys.exit(main())
