"""T-1784 mutation controls in a disposable copy.

    python mutate1784.py <copy-root> <evidence-dir> <scratch-profile>

Each mutation names the tests that must go red; control and mutations run
REPEATS times in fresh interpreters; the copy is restored after each one.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPEATS = 3
MODULE = "test_t1784_dry_run_verdict"
IMPROVE = "tools/improve.py"
CLI = "tools/saipen.py"

T = "test_"
CC_REFUSES = T + "cycle_complete_plan_refuses_a_failing_bar"
CC_MATCH = T + "cycle_complete_plan_matches_a_met_bar"
ABORT_REFUSES = T + "abort_plan_refuses_a_started_sweep"
ABORT_MATCH = T + "abort_plan_matches_a_stuck_draft"
RETIRE_REFUSES = T + "retire_plan_refuses_the_last_reportable_seat"
RETIRE_MATCH = T + "retire_plan_matches_a_spare_seat"
COMPLETE_REFUSES = T + "complete_plan_refuses_an_unmet_completion_bar"
COMPLETE_MATCH = T + "complete_plan_matches_a_report_that_meets_its_bar"
SUBMIT = T + "submit_plan_refuses_what_append_refuses_and_plans_the_rest"
REBIND_REFUSES = T + "rebind_plan_refuses_a_current_identity"
REBIND_MATCH = T + "rebind_plan_matches_a_moved_protocol_identity"
STALE_MATCH = T + "stale_complete_supersession_plan_matches_the_binding"


def drop(call: str) -> tuple[str, str]:
    """The CLI forgets to carry dry_run into one mutator call."""
    return (call, call.replace(", dry_run=dry_run", "").replace("\n                    cycle, args[2], replacement, dry_run=dry_run\n", "\n                    cycle, args[2], replacement\n"))


MUTATIONS = {
    "control": ({}, set()),
    "the engine before this Work": (
        "before",
        {CC_REFUSES, ABORT_REFUSES, RETIRE_REFUSES, COMPLETE_REFUSES, SUBMIT, REBIND_REFUSES},
    ),
    "the bar is skipped for a plan": (
        {IMPROVE: [(
            "    errors = verify_cycle(cycle_dir)\n    if errors:\n        raise ImproveError(\n"
            '            "complete_cycle refused',
            "    errors = [] if dry_run else verify_cycle(cycle_dir)\n    if errors:\n        raise ImproveError(\n"
            '            "complete_cycle refused',
        )]},
        {CC_REFUSES},
    ),
    "submit writes under a dry run": (
        {CLI: [drop("            result = _append_run(report, run_text, dry_run=dry_run)\n")]},
        {SUBMIT},
    ),
    "complete writes under a dry run": (
        {CLI: [drop("            result = _complete_report(report, dry_run=dry_run)\n")]},
        {COMPLETE_MATCH},
    ),
    "rebind writes under a dry run": (
        {CLI: [drop("            result = _rebind_report_protocol(report, dry_run=dry_run)\n")]},
        {REBIND_MATCH},
    ),
    "cycle-complete writes under a dry run": (
        {CLI: [drop("            result = complete_cycle(cycle, dry_run=dry_run)\n")]},
        {CC_MATCH},
    ),
    "abort writes under a dry run": (
        {CLI: [drop("            result = _abort_cycle(cycle, dry_run=dry_run)\n")]},
        {ABORT_MATCH},
    ),
    "retire writes under a dry run": (
        {CLI: [drop("                result = _retire_seat(cycle, args[2], reason, dry_run=dry_run)\n")]},
        {RETIRE_MATCH},
    ),
    "supersession writes under a dry run": (
        {CLI: [drop(
            "                result = _resolve_stale_complete_seat(\n"
            "                    cycle, args[2], replacement, dry_run=dry_run\n"
            "                )\n"
        )]},
        {STALE_MATCH},
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
    files = (IMPROVE, CLI)
    pristine = {name: (copy / name).read_bytes() for name in files}
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
                for item in files:
                    (copy / item).write_bytes((evidence / "before" / Path(item).name).read_bytes())
            else:
                for item, pairs in edit.items():
                    raw = pristine[item]
                    crlf = b"\r\n" in raw
                    text = raw.decode("utf-8").replace("\r\n", "\n")
                    for old, new in pairs:
                        if text.count(old) != 1 or old == new:
                            raise RuntimeError(f"anchor not unique or no-op in {item}: {old.strip()[:70]!r}")
                        text = text.replace(old, new)
                    (copy / item).write_bytes(
                        (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
                    )
            runs = [run_once(copy, env) for _ in range(REPEATS)]
        finally:
            for item, raw in pristine.items():
                (copy / item).write_bytes(raw)
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
