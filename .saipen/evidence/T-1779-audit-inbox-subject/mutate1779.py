"""T-1779 mutation controls in a disposable copy.

    python mutate1779.py <copy-root> <evidence-dir> <scratch-profile>

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
MODULE = "test_t1779_family_ignores_inbox"
SUBJECT = "tools/saipen_engine/core_unit.py"

DROP = "test_a_drop_into_the_inbox_leaves_the_fingerprint"
BELOW = "test_an_audit_directory_below_the_top_level_is_subject"
COPY = "test_the_sandbox_copy_holds_no_inbox_and_matches_the_fingerprint"

FP = "        if here == base:\n            ignored |= set(FINGERPRINT_EXCLUDED) | set(FAMILY_INPUT_EXCLUDED)\n"
CP = "            ignored |= set(FAMILY_INPUT_EXCLUDED) & set(names)\n"

MUTATIONS = {
    "control": (None, set()),
    "the family before this Work": ("before", {DROP, COPY}),
    "the copy still takes the inbox": ((CP, ""), {COPY}),
    "the fingerprint still takes the inbox": (
        (FP, "        if here == base:\n            ignored |= set(FINGERPRINT_EXCLUDED)\n"),
        {DROP, COPY},
    ),
    "every level drops audit": (
        (FP, "        ignored |= set(FAMILY_INPUT_EXCLUDED)\n        if here == base:\n"
             "            ignored |= set(FINGERPRINT_EXCLUDED)\n"),
        {BELOW},
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
                target.write_bytes((evidence / "before" / "core_unit.py").read_bytes())
            elif edit is not None:
                old, new = edit
                text = pristine.decode("utf-8").replace("\r\n", "\n")
                if text.count(old) != 1:
                    raise RuntimeError(f"anchor not unique for {name!r}")
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
