"""Capture exact hot-switch verification commands without changing source files."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SUBJECTS = (
    "tools/saipen_engine/oracle.py",
    "tools/test_t1707_regression_chronology.py",
    "tools/saipen_engine/guard_events.py",
    "tools/saipen_engine/admission.py",
    "tools/test_t1705_lifecycle_write_preflight.py",
    "tools/test_opencode_bound_launch_smoke.py",
    "extensions/adapters/opencode/saipen-guard.js",
    "saipen/CORE.md",
    "saipen/OPS.md",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    parser.add_argument("--timeout", type=int, default=5400)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("an exact command is required")
    if Path(args.label).name != args.label:
        parser.error("label must be a filename")
    output = HERE / f"{args.label}.txt"
    receipt = HERE / f"{args.label}.json"
    if output.exists() or receipt.exists():
        parser.error("existing evidence is immutable; choose a new label")
    start = datetime.now(timezone.utc).isoformat()
    before = {name: digest(ROOT / name) for name in SUBJECTS}
    tick = time.monotonic()
    with output.open("wb") as stream:
        result = subprocess.run(
            command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
            check=False, timeout=args.timeout,
        )
    after = {name: digest(ROOT / name) for name in SUBJECTS}
    record = {
        "command": command,
        "cwd": str(ROOT),
        "started_utc": start,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "duration_s": round(time.monotonic() - tick, 3),
        "exit_code": result.returncode,
        "output": str(output.relative_to(ROOT)).replace("\\", "/"),
        "output_sha256": digest(output),
        "subject_before": before,
        "subject_after": after,
        "subject_unchanged": before == after,
    }
    receipt.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8", errors="replace"))
    print(json.dumps({key: record[key] for key in (
        "exit_code", "duration_s", "output", "subject_unchanged",
    )}))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
