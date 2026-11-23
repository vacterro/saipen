"""T-1761 mutation controls, run in a disposable copy of the tree.

    python mutate1761.py <copy-root> <evidence-dir> <scratch-profile>

Each mutation names the tests that must go red, across the new module and the
T-1759 module whose behaviour case this Work changed. The control and every
mutation run REPEATS times in fresh interpreters; a test red in some
repetitions only is reported as flaky. The copy is restored after each one.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPEATS = 3
MODULES = ("test_t1761_recovery_reaches_a_typed_duplicate", "test_t1759_single_lifecycle_observer")
AUTHORITY = "tools/saipen_engine/lifecycle_authority.py"
BOARD = "tools/saipen_engine/board.py"
RECONCILE = "tools/saipen_engine/reconcile.py"
SUBJECTS = (AUTHORITY, BOARD, RECONCILE)

ROUTE = "test_the_printed_decision_runs_and_the_typed_closure_is_not_buried"
NOTHING = "test_a_decision_on_a_head_operations_wrote_carries_nothing"
LINES = "test_typed_lines_and_a_second_record_are_followed_through_the_rename"
BARE = "test_a_second_record_with_no_other_trace_is_judged_too"
FORGED = "test_a_typed_carry_clause_judges_nothing_an_operation_holds"
ROWS = "test_only_an_unauthorized_verdict_has_rows_to_carry"
BURIES = "test_the_decision_over_a_typed_head_buries_nothing"
READERS = "test_only_repairing_readers_name_the_lifecycle_class"

#: name -> (edits, tests that must go red). An edit is (file, old, new), or
#: (file, None, None) to put the pre-fix bytes of that file back.
MUTATIONS = {
    "control": ([], set()),
    "the engine before this Work": (
        [(AUTHORITY, None, None), (BOARD, None, None), (RECONCILE, None, None)],
        {ROUTE, NOTHING, LINES, BARE, FORGED, ROWS, BURIES, READERS},
    ),
    "reads past the head and carries nothing": (
        [(RECONCILE,
          '            + (f". {_authority.carry_note(carried)}" if carried else "")\n',
          "")],
        {ROUTE, LINES, BARE, BURIES},
    ),
    "the carry is written and never read back": (
        [(AUTHORITY, 'CARRY_OP_CLASS = "duplicate-id-"\n', 'CARRY_OP_CLASS = "no-such-class-"\n')],
        {ROUTE, LINES, BARE, BURIES},
    ),
    "a record renamed under DONE is not carried": (
        [(RECONCILE,
          '        docs.get("_lifecycle"), new_id if loser["section"] == "## DONE" else None\n',
          '        docs.get("_lifecycle"), None\n')],
        {LINES, BARE},
    ),
    "a record behind a live id is not a row": (
        [(AUTHORITY,
          '    return row.get("section") == "## DONE" or "## DONE" in (row.get("shadowed") or ())\n',
          '    return row.get("section") == "## DONE"\n')],
        {LINES, BARE},
    ),
    "any verdict has rows to carry": (
        [(AUTHORITY,
          '    if not isinstance(verdict, dict) or verdict.get("status") != UNAUTHORIZED:\n'
          "        return []\n",
          "    if not isinstance(verdict, dict):\n"
          "        return []\n")],
        {ROWS},
    ),
}


def run_once(copy: Path, env: dict) -> tuple[set, int]:
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", *MODULES, "-v"],
        cwd=copy / "tools", env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=1500,
    )
    red = set(re.findall(r"^(?:FAIL|ERROR): (\w+) ", done.stderr, re.MULTILINE))
    ran = re.search(r"^Ran (\d+) test", done.stderr, re.MULTILINE)
    if ran is None:
        raise RuntimeError("no unittest summary:\n" + done.stderr[-1500:])
    return red, int(ran.group(1))


def main(argv: list[str]) -> int:
    copy, evidence, profile = (Path(item).resolve() for item in argv[:3])
    env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    env.update(
        USERPROFILE=str(profile), HOME=str(profile), CLAUDE_CONFIG_DIR=str(profile / ".claude"),
        PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
    )
    pristine = {name: (copy / name).read_bytes() for name in SUBJECTS}
    problems = 0
    for name, (edits, expected) in MUTATIONS.items():
        try:
            for target, old, new in edits:
                path = copy / target
                if old is None:
                    path.write_bytes((evidence / "before" / Path(target).name).read_bytes())
                    continue
                raw = path.read_bytes()
                text = raw.decode("utf-8").replace("\r\n", "\n")
                if text.count(old) != 1:
                    raise RuntimeError(f"anchor not unique for {name!r}: {old.strip()[:80]!r}")
                text = text.replace(old, new)
                path.write_bytes(
                    (text.replace("\n", "\r\n") if b"\r\n" in raw else text).encode("utf-8")
                )
            runs = [run_once(copy, env) for _ in range(REPEATS)]
        finally:
            for target, raw in pristine.items():
                (copy / target).write_bytes(raw)
        reds = [red for red, _ in runs]
        stable = all(red == reds[0] for red in reds)
        verdict = "as expected" if stable and reds[0] == expected else "UNEXPECTED"
        if not stable:
            verdict = "FLAKY"
        if verdict != "as expected":
            problems += 1
        print(f"{name}: ran {runs[0][1]}, red {len(reds[0])} -- {verdict}")
        if verdict != "as expected":
            print(f"    expected: {sorted(expected)}")
            print(f"    got:      {[sorted(r) for r in reds]}")
    print(f"mutations: {len(MUTATIONS) - 1}, repetitions each: {REPEATS}, problems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
