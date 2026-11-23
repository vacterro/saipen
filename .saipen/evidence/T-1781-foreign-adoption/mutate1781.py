"""T-1781 mutation controls in a disposable copy.

    python mutate1781.py <copy-root> <evidence-dir> <scratch-profile>

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
OPS = "tools/saipen_engine/operations.py"
FALLBACK = "tools/saipen_engine/continue_fallback.py"
CLI = "tools/saipen.py"

LATER_PATCH = "test_a_later_patch_build_closes_as_its_own_patch"
LATER_NO_DELTA = "test_a_later_no_delta_build_still_refuses_own_patch"
WIRING = "test_the_continue_fallthrough_wires_the_liveness_in"
T36 = {
    "test_help_prints_the_closed_set",
    "test_the_validation_detail_prints_the_same_set",
    "test_usage_and_refusal_cannot_drift",
}
T37 = {
    "test_own_patch_refuses_a_no_delta_build_and_names_the_alternates",
    "test_the_no_delta_build_record_is_found",
}
T38 = {
    WIRING,
    "test_a_complete_report_with_a_run_block_is_not_stale",
    "test_a_young_draft_is_reported_but_not_stale",
    "test_an_unfinished_report_on_a_cycle_that_left_flight_is_stale",
    "test_an_unknown_cycle_says_nothing",
    "test_the_measured_stale_cycle_is_reported_as_stale_work",
    "test_a_different_stale_cycle_rides_along",
    "test_a_stale_cycle_is_visible_with_no_assigned_cycle_at_all",
    "test_an_unknown_cycle_leaves_the_answer_alone",
    "test_the_answer_carries_the_assigned_cycle",
    "test_the_marker_names_the_cycle_when_the_answer_does_not",
}

GUARD = (
    '    if _mode == "own_patch" and latest_build_declares_no_delta(\n'
    '        ticket_id, docs["_history"].events\n'
    "    ):\n"
)

MUTATIONS = {
    "control": ({}, set()),
    "the engine before the foreign edits": ("before", T36 | T37 | T38 | {LATER_NO_DELTA}),
    "the foreign guard reads every BUILD": (
        {OPS: [(GUARD, '    if _mode == "own_patch" and no_delta_build_events(ticket_id, docs["_history"].events):\n')]},
        {LATER_PATCH},
    ),
    "the first BUILD decides": (
        {OPS: [("bool(_NO_DELTA_BUILD_RE.search(str(builds[-1].get", "bool(_NO_DELTA_BUILD_RE.search(str(builds[0].get")]},
        {LATER_PATCH, LATER_NO_DELTA},
    ),
    "the liveness is not wired into continue": (
        {CLI: [("        payload = with_cycle_liveness(payload, project_root)\n", "")]},
        {WIRING},
    ),
    "the usage hides the taxonomy again": (
        {CLI: [
            ('"transition <PHASE> [T-###] [text]|checkpoint <DEC|RUN> "', '"transition <PHASE> [T-###] [text]|checkpoint <TAXONOMY> "'),
            ('"detail": "checkpoint needs <DEC|RUN> [T-###] [text]",', '"detail": "checkpoint needs <TAXONOMY> [T-###] [text]",'),
        ]},
        T36,
    ),
}


def run_once(copy: Path, env: dict) -> tuple[set, int]:
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tools", "-p", "test_*t3[678]_*.py", "-v"],
        cwd=copy,
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
    files = (OPS, FALLBACK, CLI)
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
                        if text.count(old) != 1:
                            raise RuntimeError(f"anchor not unique in {item}: {old.strip()[:70]!r}")
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
