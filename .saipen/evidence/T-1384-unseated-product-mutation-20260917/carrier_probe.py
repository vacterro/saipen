"""Does `input.sessionID` reach the guard on EVERY consequential tool event?

T-1384's binding is only buildable if the host supplies a session identity the
guard can see every single time it judges a mutation. The adapter has passed
`input.sessionID` into the event since T-1318 (saipen-guard.js:625) and the
engine dropped it, so the field has never been watched arriving. The operator's
instruction is explicit: do not invent an identity field the host cannot
reliably supply.

This probe answers that question from the REAL adapter path -- one live
OpenCode session against the installed runtime, in a throwaway worktree
fixture -- and never from the adapter's source.

Method: `SAIPEN_GUARD_EVENT_PROBE` names a file the guard appends one JSON line
to per event it judged. The probe drives one ordinary session, then reports,
for every consequential event:

    how many events carried a non-empty session_id
    how many distinct session_id values appeared
    whether the value is stable across the whole session

PASS requires: at least one consequential event, every consequential event
carrying a session_id, and exactly one distinct value.

    python .saipen/evidence/T-1384-.../carrier_probe.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

REPO = Path.cwd()
sys.path.insert(0, str(REPO / "tools"))

import t1363_field_polygon as polygon  # noqa: E402
import test_t1363_zero_manual_entry as fixtures  # noqa: E402

TASK = "add a one-line docstring to the top of src/app.py"
#: Tool identities whose effect can change the project. A read carrying no
#: session id would be a gap worth knowing about but would not block the
#: binding; a MUTATION carrying none makes the binding unbuildable.
CONSEQUENTIAL = {"edit", "write", "patch", "bash", "multiedit"}


class _Case(unittest.TestCase):
    def runTest(self) -> None:  # pragma: no cover
        pass


def main() -> int:
    opencode = shutil.which("opencode")
    if not opencode:
        print("opencode runtime unavailable -- carrier UNPROVEN, not FAILED")
        return 3

    here = Path(__file__).resolve().parent
    trace = here / "carrier-probe-events.jsonl"
    if trace.exists():
        trace.unlink()

    project = fixtures.healthy(_Case())
    env = dict(os.environ)
    env.update(polygon._task_env(project, TASK))
    env["SAIPEN_GUARD_EVENT_PROBE"] = str(trace)

    proc = subprocess.run(
        [opencode, "run", TASK, "--format", "json", "--auto", "--model", "sairoute/SAIFREN"],
        cwd=str(project),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1200,
    )

    print("## Session")
    print(f"project    : {project}")
    print(f"returncode : {proc.returncode}")
    print(f"stderr tail: {proc.stderr[-300:]!r}")
    print()

    if not trace.is_file():
        print("RED: the guard wrote no event trace -- SAIPEN_GUARD_EVENT_PROBE never fired")
        return 1

    rows = []
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    consequential = [r for r in rows if str(r.get("tool_name", "")).lower() in CONSEQUENTIAL]
    with_id = [r for r in consequential if r.get("session_id")]
    values = Counter(r.get("session_id") for r in consequential)

    print("## Carrier")
    print(f"events judged            : {len(rows)}")
    print(f"consequential events     : {len(consequential)}")
    print(f"  carrying a session_id  : {len(with_id)}")
    print(f"  distinct values        : {sorted(v for v in values if v)}")
    print(f"  missing on             : {[r.get('tool_name') for r in consequential if not r.get('session_id')]}")
    print(f"read/other events        : {len(rows) - len(consequential)}")
    print()

    distinct = {v for v in values if v}
    ok = bool(consequential) and len(with_id) == len(consequential) and len(distinct) == 1

    print("## Verdict")
    if not consequential:
        print("UNPROVEN: the session judged no consequential event -- nothing to bind")
        return 2
    if not ok:
        print("RED: the host does not supply one stable session identity on every")
        print("     consequential event -- do NOT build the binding on this field")
        return 1
    print("GREEN: every consequential event carried the same session identity;")
    print("       the carrier survives the real adapter path and is bindable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
