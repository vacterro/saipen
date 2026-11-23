"""T-1775 mutation controls in a disposable copy.

    python mutate1775.py <copy-root> <evidence-dir> <scratch-profile>

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
MODULE = "test_t1775_continue_never_admits_a_seat"
FALLBACK = "tools/saipen_engine/continue_fallback.py"
CLI = "tools/saipen.py"

COMPLETE = "test_a_complete_roster_routes_to_the_core_sweep"
OBEY = "test_obeying_the_router_on_a_complete_roster_never_grows_it"
DRAFT = "test_an_incomplete_seat_of_this_family_resumes_by_its_session"
BAR = "test_a_met_bar_routes_to_completion"
FOREIGN = "test_another_agents_incomplete_seat_is_not_taken_over"
DETAIL = "test_the_detail_no_longer_advises_the_bare_form"
FAULT = "test_an_unreadable_cycle_answers_read_only"
ALL = {COMPLETE, OBEY, DRAFT, BAR, FOREIGN, DETAIL, FAULT}

#: name -> (edits {file: [(old, new)]} or "before", tests that must go red)
MUTATIONS = {
    "control": ({}, set()),
    "the engine before this Work": ("before", ALL),
    "the own seat is ignored": (
        {FALLBACK: [("        if own:\n", "        if False:\n")]},
        {DRAFT},
    ),
    "another family's seat routes to the sweep": (
        {FALLBACK: [("        if foreign:\n", "        if False:\n")]},
        {FOREIGN},
    ),
    "the bar test is inverted": (
        {FALLBACK: [("        if verify_cycle(cycle):\n", "        if not verify_cycle(cycle):\n")]},
        {COMPLETE, OBEY, BAR},
    ),
    "the family is misread": (
        {FALLBACK: [
            ("(own if seat.startswith(family + \"-\") else foreign).append(seat)",
             "(own if seat.startswith(\"nobody-\") else foreign).append(seat)"),
        ]},
        {DRAFT},
    ),
    "a fault admits a seat": (
        {FALLBACK: [
            ("    except Exception as exc:  # any fault answers read-only; this route never admits\n"
             "        return (\n            \"saipen improve status\",\n",
             "    except Exception as exc:  # any fault answers read-only; this route never admits\n"
             "        return (\n            \"saipen improve\",\n"),
        ]},
        {FAULT},
    ),
    "the emission keeps the bare form": (
        {CLI: [('                    "action": _resume,\n', '                    "action": "saipen improve",\n')]},
        {COMPLETE, OBEY, DRAFT, BAR, FOREIGN, FAULT},
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
    files = (FALLBACK, CLI)
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
