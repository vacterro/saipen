#!/usr/bin/env python
"""Prove every check in the portable floor can still go red.

`tests/validate.sh` is what a host without Python runs INSTEAD of
tools/validate.py. Its checks were verified by hand when they shipped and
nothing kept them verified -- the same shape as the LOG timestamp check that
lay dead in validate.py from feae149 to v7.99.0, and as the first draft of the
portable-floor drift check, which passed its own red test by accident because
it could never fail at all.

So: build a known-good scratch project, break it one way per check, and assert
the floor names that specific failure. A check nobody has seen fire is
indistinguishable from one that cannot.

Stdlib only, same rule as the validator. Run from the SAIPEN home:

    python tools/audit_floor.py

The PowerShell half is deliberately out of scope here. CI executes
tests/validate.ps1 against this repo every run, which proves it runs clean on
a conformant project; it does not prove its individual checks still fire. That
gap is stated rather than papered over.
"""

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
FLOOR = HOME / "tests" / "validate.sh"

GOOD_STATE = """---
phase: PLAN
task: none
next_action: "saipen plan"
blocker: none
transition_from: INIT
saipen_version: 7
schema_version: 1
agent: test
mode: full
updated: 2026-07-28T10:00:00Z
---
"""
GOOD_BOARD = ("# Board\n## DOING\n\n## TODO\n- [ ] T-001 a ticket\n\n"
              "## DONE\n\n## BLOCKED\n")
GOOD_LOG = "# Log\n\n- 28.07.26 10:00 [E-001] [T-none] DEC: fixture\n"


def find_bash():
    """A plain "bash" is wrong on Windows: from Python it resolves to the WSL
    stub, which without an installed distro prints a UTF-16 error and runs
    nothing. The first version of this audit reported every check dead because
    of exactly that -- the instrument, not the floor."""
    for candidate in (r"C:\Program Files\Git\usr\bin\bash.exe",
                      r"C:\Program Files\Git\bin\bash.exe"):
        if os.path.isfile(candidate):
            return candidate
    found = shutil.which("bash")
    if found and "System32" not in found:
        return found
    return found


# (label, mutate(state, board, log) -> (state, board, log), expected substring)
# A None value means "do not write this file at all".
CASES = [
    ("missing STATE.md", lambda s, b, lg: (None, b, lg), "STATE.md missing"),
    ("missing BOARD.md", lambda s, b, lg: (s, None, lg), "BOARD.md missing"),
    ("missing LOG.md", lambda s, b, lg: (s, b, None), "LOG.md missing"),
    ("no phase", lambda s, b, lg: (re.sub(r"phase: PLAN\n", "", s, 1), b, lg),
     "missing valid phase"),
    ("no task", lambda s, b, lg: (s.replace("task: none\n", "", 1), b, lg),
     "missing task"),
    ("no next_action",
     lambda s, b, lg: (re.sub(r"next_action: .*\n", "", s, 1), b, lg),
     "missing next_action"),
    ("no blocker", lambda s, b, lg: (s.replace("blocker: none\n", "", 1), b, lg),
     "missing blocker"),
    ("no agent", lambda s, b, lg: (s.replace("agent: test\n", "", 1), b, lg),
     "missing agent"),
    ("no updated",
     lambda s, b, lg: (re.sub(r"updated: .*\n", "", s, 1), b, lg), "missing updated"),
    ("bad mode", lambda s, b, lg: (s.replace("mode: full", "mode: banana", 1), b, lg),
     "missing mode"),
    ("no saipen_version",
     lambda s, b, lg: (s.replace("saipen_version: 7\n", "", 1), b, lg),
     "missing saipen_version"),
    ("no transition_from",
     lambda s, b, lg: (s.replace("transition_from: INIT\n", "", 1), b, lg),
     "missing transition_from"),
    ("read-only in BUILD",
     lambda s, b, lg: (s.replace("mode: full", "mode: read-only", 1)
                      .replace("phase: PLAN", "phase: BUILD", 1), b, lg),
     "read-only MUST NOT enter"),
    ("goal_mode without goal_waves",
     lambda s, b, lg: (s.replace("mode: full",
                                "mode: full\ngoal_mode: true\ngoal_tickets: 0", 1), b, lg),
     "goal_waves counter missing"),
    ("goal_mode without goal_tickets",
     lambda s, b, lg: (s.replace("mode: full",
                                "mode: full\ngoal_mode: true\ngoal_waves: 0", 1), b, lg),
     "goal_tickets counter missing"),
    ("cyclic needs",
     lambda s, b, lg: (s, "# Board\n## DOING\n\n## TODO\n- [ ] T-001 a | needs: T-002\n"
                         "- [ ] T-002 b | needs: T-001\n\n## DONE\n\n## BLOCKED\n", lg),
     "cyclic needs"),
    ("duplicate ticket ID",
     lambda s, b, lg: (s, "# Board\n## DOING\n\n## TODO\n- [ ] T-001 a\n"
                         "- [ ] T-001 b\n\n## DONE\n\n## BLOCKED\n", lg),
     "duplicate ticket ID"),
    ("dangling needs",
     lambda s, b, lg: (s, "# Board\n## DOING\n\n## TODO\n- [ ] T-001 a | needs: T-999\n"
                         "\n## DONE\n\n## BLOCKED\n", lg),
     "dangling needs"),
    ("missing BOARD heading",
     lambda s, b, lg: (s, "# Board\n## DOING\n\n## TODO\n\n## DONE\n", lg),
     "missing required section heading"),
    ("malformed LOG line",
     lambda s, b, lg: (s, b, "# Log\n\n- this is not an event line at all\n"),
     "Graph Event format"),
]


def main():
    if not FLOOR.is_file():
        print(f"FAIL: {FLOOR.as_posix()} not found")
        return 1
    bash = find_bash()
    if not bash:
        print("SKIP: no usable bash on this host -- the portable floor cannot "
              "be audited here (this is not a pass)")
        return 0

    failures = []
    for label, mutate, expect in CASES:
        work = Path(tempfile.mkdtemp(prefix="saipen-floor-"))
        try:
            (work / ".saipen").mkdir()
            state, board, log = mutate(GOOD_STATE, GOOD_BOARD, GOOD_LOG)
            for name, content in (("STATE.md", state), ("BOARD.md", board),
                                  ("LOG.md", log)):
                if content is not None:
                    with io.open(work / ".saipen" / name, "w",
                                 encoding="utf-8", newline="\n") as fh:
                        fh.write(content)
            r = subprocess.run([bash, FLOOR.as_posix()], cwd=str(work),
                               capture_output=True, text=True)
            blob = r.stdout + r.stderr
            if expect not in blob:
                first = next((ln for ln in blob.splitlines() if "FAIL" in ln),
                             "<no FAIL line at all>")
                failures.append(f"{label}: expected {expect!r}, got {first[:100]!r}")
            elif r.returncode == 0:
                failures.append(f"{label}: named the failure but exited 0")
            else:
                print(f"PASS: {label} -- floor reports {expect!r}")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    print(f"\n{len(CASES)} portable-floor checks exercised")
    if failures:
        print(f"\nFAILED: {len(failures)} check(s) did not fire as expected")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("Every portable-floor check still goes red on its own condition.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
