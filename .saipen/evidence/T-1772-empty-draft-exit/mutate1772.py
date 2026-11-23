"""T-1772 mutation controls in a disposable copy.

    python mutate1772.py <copy-root> <evidence-dir> <scratch-profile>

Each mutation names the tests that must go red; the control and every mutation
run REPEATS times in fresh interpreters, a test red in some repetitions only is
reported as flaky, and the copy is restored after each one. Profile carriers
are redirected so no run reaches the operator's real profile.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPEATS = 3
MODULE = "test_t1772_empty_draft_exit"
SUBJECT = "tools/improve.py"

NAMES = "test_reconcile_names_the_sanctioned_exit"
PLAN = "test_its_plan_names_the_same_exit"
PRINTED = "test_the_printed_exit_terminates_the_cycle_and_keeps_every_report_byte"
BESIDE = "test_an_empty_draft_beside_evidence_still_retires"
RETIRED = "test_a_retired_seat_is_not_a_survivor"

GUARD = "    if empty and not survivors:\n"
RULE = '        if record["availability"] != "unavailable" and record["class"] != "EMPTY_DRAFT"\n'
ROUTE = '            "canonical_next_command": f"saipen improve abort {cycle_dir.name}",\n'

#: name -> ((old, new) inside the subject, or "before"), tests that must go red
MUTATIONS = {
    "control": (None, set()),
    "the engine before this Work": ("before", {NAMES, PLAN, PRINTED, RETIRED}),
    "the check never fires": ((GUARD, "    if False:\n"), {NAMES, PLAN, PRINTED, RETIRED}),
    "the plan skips the check": ((GUARD, "    if empty and not survivors and not dry_run:\n"), {PLAN}),
    "the check fires beside evidence": ((GUARD, "    if empty:\n"), {BESIDE}),
    "a retired seat counts as a survivor": (
        (RULE, '        if record["class"] != "EMPTY_DRAFT"\n'),
        {RETIRED},
    ),
    "the route names reconcile again": (
        (ROUTE, '            "canonical_next_command": f"saipen improve reconcile {cycle_dir.name}",\n'),
        {NAMES, PLAN, PRINTED, RETIRED},
    ),
}


def run_once(copy: Path, env: dict) -> tuple[set, int]:
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", MODULE, "-v"],
        cwd=copy / "tools",
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    red = set(re.findall(r"^(?:FAIL|ERROR): (\w+) ", done.stderr, re.MULTILINE))
    ran = re.search(r"^Ran (\d+) test", done.stderr, re.MULTILINE)
    if ran is None:
        raise RuntimeError("no unittest summary:\n" + done.stderr[-1500:])
    return red, int(ran.group(1))


def main(argv: list[str]) -> int:
    copy, evidence, profile = (Path(item).resolve() for item in argv[:3])
    target = copy / SUBJECT
    pristine = target.read_bytes()
    crlf = b"\r\n" in pristine
    env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    env.update(
        USERPROFILE=str(profile),
        HOME=str(profile),
        CLAUDE_CONFIG_DIR=str(profile / ".claude"),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONIOENCODING="utf-8",
    )
    problems = 0
    for name, (edit, expected) in MUTATIONS.items():
        try:
            if edit == "before":
                target.write_bytes((evidence / "before" / "improve.py").read_bytes())
            elif edit is not None:
                old, new = edit
                text = pristine.decode("utf-8").replace("\r\n", "\n")
                if text.count(old) != 1:
                    raise RuntimeError(f"anchor not unique for {name!r}: {old.strip()[:70]!r}")
                text = text.replace(old, new)
                target.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
            runs = [run_once(copy, env) for _ in range(REPEATS)]
        finally:
            target.write_bytes(pristine)
        reds = [red for red, _ in runs]
        stable = all(red == reds[0] for red in reds)
        verdict = "as expected" if stable and reds[0] == expected else "UNEXPECTED"
        if not stable:
            verdict = "FLAKY"
        if verdict != "as expected":
            problems += 1
        print(f"{name}: ran {runs[0][1]}, red {len(reds[0])} -- {verdict}", flush=True)
        if verdict != "as expected":
            print(f"    expected: {sorted(expected)}")
            print(f"    got:      {[sorted(r) for r in reds]}")
    print(f"mutations: {len(MUTATIONS) - 1}, repetitions each: {REPEATS}, problems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
