"""T-1782 mutation controls in a disposable copy.

    python mutate1782.py <copy-root> <evidence-dir> <scratch-profile>

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
MODULES = ["test_t1782_capped_builder_identifier", "test_t1326_board_compaction.CanonicalLogProducerTests"]
SUBJECT = "tools/test_t1326_board_compaction.py"

NAME = "test_a_name_that_contains_the_builder_is_not_a_reach"
REACH = "test_every_direct_reach_is_still_an_offender"
COMMENT = "test_a_comment_is_not_a_reach"
LIVE = "test_no_engine_module_calls_the_capped_builder_directly"
PATTERN = '_CAPPED_BUILDER = re.compile(r"(?<![A-Za-z0-9_])build_event(?![A-Za-z0-9_])")\n'

MUTATIONS = {
    "control": (None, set()),
    "the check before this Work": ("before", {"test_t1782_capped_builder_identifier", LIVE}),
    "no left boundary": (
        (PATTERN, '_CAPPED_BUILDER = re.compile(r"build_event(?![A-Za-z0-9_])")\n'),
        {NAME},
    ),
    "no right boundary": (
        (PATTERN, '_CAPPED_BUILDER = re.compile(r"(?<![A-Za-z0-9_])build_event")\n'),
        {NAME},
    ),
    "comments count": (
        ('        if _CAPPED_BUILDER.search(line.split("#", 1)[0])\n',
         "        if _CAPPED_BUILDER.search(line)\n"),
        {COMMENT, LIVE},
    ),
    "a call is required": (
        (PATTERN, '_CAPPED_BUILDER = re.compile(r"(?<![A-Za-z0-9_])build_event\\(")\n'),
        {REACH},
    ),
}


def run_once(copy: Path, env: dict) -> tuple[set, int]:
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", *MODULES, "-v"],
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
                target.write_bytes((evidence / "before" / Path(SUBJECT).name).read_bytes())
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
