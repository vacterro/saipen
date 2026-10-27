"""Red-before-green control for the T-1862 display contract.

Builds the reported shape on a disposable project, then runs the SAME fixture
against the engine as it stands in HEAD (pre-change) and the working tree
(post-change). The pre-change run must show no readiness at all -- in JSON and
in the human render -- and the post-change run must show AUDIT_OUTSTANDING in
both. A green pair where either half is missing fails this control.

Run: python tools/control_t1862_display.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

BASE_TEXT = subprocess.run(
    ["git", "show", "HEAD:tools/saipen.py"], cwd=str(TOOLS.parent),
    capture_output=True, text=True, encoding="utf-8", check=True,
).stdout


def _build(case: unittest.TestCase) -> Path:
    from test_t1363_zero_manual_entry import project

    root = project(
        case,
        execution_intent="goal",
        goal_waves=0,
        goal_tickets=0,
        continuation_authority="operator_required",
        authority_source="E-1",
        authority_until="budget",
        safety_valve_mode="hard_wait",
    )
    (root / "audit").mkdir()
    (root / "audit" / "1.md").write_text(
        "# audit layer\n\nOne unconsumed generation.\n", encoding="utf-8"
    )
    return root


def _run(engine: Path, root: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["SAIPEN_HOME"] = str(TOOLS.parent)
    return subprocess.run(
        [sys.executable, "-B", str(engine), *args],
        cwd=str(root), capture_output=True, text=True, encoding="utf-8", env=env, timeout=180,
    )


def main() -> int:
    case = unittest.TestCase()
    root = _build(case)
    base_engine = TOOLS / "_control_base_saipen.py"
    base_engine.write_text(BASE_TEXT, encoding="utf-8")
    try:
        red_json = _run(base_engine, root, "status", "--json")
        red_human = _run(base_engine, root, "status")
        green_json = _run(TOOLS / "saipen.py", root, "status", "--json")
        green_human = _run(TOOLS / "saipen.py", root, "status")
    finally:
        base_engine.unlink(missing_ok=True)

    checks = []
    for label, proc in (
        ("red-json", red_json), ("red-human", red_human),
        ("green-json", green_json), ("green-human", green_human),
    ):
        if proc.returncode != 0:
            print(f"CONTROL BROKEN: {label} exited {proc.returncode}: {proc.stderr[-400:]}")
            return 2

    red_payload = json.loads(red_json.stdout)
    green_payload = json.loads(green_json.stdout)
    checks.append((
        "pre-change JSON carries no readiness",
        "readiness" not in red_payload,
    ))
    checks.append((
        "pre-change human output names no readiness",
        "Readiness:" not in red_human.stdout,
    ))
    checks.append((
        "pre-change human output is exactly the phase verdict",
        "phase: DONE" in red_human.stdout,
    ))
    checks.append((
        "post-change JSON names AUDIT_OUTSTANDING",
        (green_payload.get("readiness") or {}).get("status") == "AUDIT_OUTSTANDING",
    ))
    checks.append((
        "post-change JSON still publishes phase DONE",
        green_payload.get("phase") == "DONE",
    ))
    checks.append((
        "post-change human output names the same status",
        "Readiness: AUDIT_OUTSTANDING" in green_human.stdout,
    ))
    checks.append((
        "post-change human output quotes the authority unchanged",
        "authority unchanged:" in green_human.stdout
        and "operator_required" in green_human.stdout,
    ))
    checks.append((
        "post-change JSON grants no authority",
        (green_payload.get("readiness") or {}).get("grants_authority") is False,
    ))

    ok = True
    for label, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {label}")
        ok = ok and passed
    print("CONTROL HOLDS" if ok else "CONTROL FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
