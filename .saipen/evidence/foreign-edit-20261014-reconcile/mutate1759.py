"""T-1759 mutation controls, run in a disposable copy of the tree.

    python mutate1759.py <copy-root> <evidence-dir> <scratch-profile>

Each mutation names the tests that must go red. The control and every mutation
run REPEATS times in fresh interpreters; a test red in some repetitions only is
reported as flaky and fails the script. The copy is restored after each one.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPEATS = 3
MODULE = "test_t1759_single_lifecycle_observer"
RECONCILE = "tools/saipen_engine/reconcile.py"
OPERATIONS = "tools/saipen_engine/operations.py"

TYPED = "test_the_decision_does_not_build_on_a_typed_head"
CONTRACT = "test_only_repairing_readers_name_the_lifecycle_class"

#: name -> (file, old, new) with old None for a whole-file replacement taken
#: from the evidence directory, and the tests that must go red.
MUTATIONS = {
    "control": (None, set()),
    "the foreign hunk": ((RECONCILE, None, "reconcile.with-foreign-hunk.py"), {TYPED, CONTRACT}),
    "a log normalizer names the class": (
        (OPERATIONS, '    read_once = _read(root, observe=("log",))\n',
         '    read_once = _read(root, observe=("log", "lifecycle_authority"))\n'),
        {CONTRACT},
    ),
    "a migration names the class through a computed value": (
        (OPERATIONS, '        root, allow_dead_home=True, observe=("state",)\n',
         '        root, allow_dead_home=True, observe=tuple(["state", "lifecycle_authority"])\n'),
        {CONTRACT},
    ),
}


def run_once(copy: Path, env: dict) -> tuple[set, int]:
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", MODULE, "-v"],
        cwd=copy / "tools", env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=900,
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
    pristine = {name: (copy / name).read_bytes() for name in (RECONCILE, OPERATIONS)}
    problems = 0
    for name, (edit, expected) in MUTATIONS.items():
        try:
            if edit is not None:
                target, old, new = edit
                path = copy / target
                if old is None:
                    path.write_bytes((evidence / new).read_bytes())
                else:
                    raw = pristine[target]
                    text = raw.decode("utf-8").replace("\r\n", "\n")
                    if text.count(old) != 1:
                        raise RuntimeError(f"anchor not unique for {name!r}: {old.strip()!r}")
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
        print(f"{name}: ran {runs[0][1]}, red {sorted(reds[0])} -- {verdict}")
        if verdict != "as expected":
            print(f"    expected red: {sorted(expected)}; all: {[sorted(r) for r in reds]}")
    print(f"mutations: {len(MUTATIONS) - 1}, repetitions each: {REPEATS}, problems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
