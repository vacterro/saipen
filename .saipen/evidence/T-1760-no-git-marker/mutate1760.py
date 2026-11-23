"""T-1760 mutation controls, run in a disposable copy of the tree.

    python mutate1760.py <copy-root> <evidence-dir> <foreign-validate.py> <scratch-profile>

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
MODULE = "test_t1760_no_git_ccc_marker"
VALIDATE = "tools/validate.py"

MARKER = "test_the_engines_own_marker_is_a_marker_without_git"
GIT_OWES = "test_a_git_project_still_owes_a_commit_id"
BOUNDARY = "test_a_skipped_publish_is_the_ship_boundary_without_git"
BEFORE = "test_a_package_prepared_before_any_ship_still_fails"
NESTED = "test_a_project_inside_another_repository_is_no_git_too"
GIT_BOUNDARY = "test_a_skipped_publish_is_no_boundary_where_a_push_can_exist"

OWNER = '            _ccc_no_git = compute_source_identity(Path(".")).source_head == "no-git"\n'
GUARD = "        if _ship_at is None and _ccc_no_git:\n"

#: name -> (edit, tests that must go red). An edit is (old, new) inside
#: validate.py, or (None, <path>) for a whole-file replacement.
MUTATIONS = {
    "control": (None, set()),
    "validator pre-fix": ((None, "before"), {MARKER, NESTED, BEFORE}),
    "the foreign variant (no-git admitted everywhere)": (
        (None, "foreign"), {GIT_OWES, BOUNDARY},
    ),
    "git's own answer decides, not the identity owner": (
        (OWNER, '            _ccc_no_git = _git("rev-parse", "--is-inside-work-tree")[0] != 0\n'),
        {NESTED},
    ),
    "the owner is never asked": (
        (OWNER, "            _ccc_no_git = True\n"), {GIT_OWES},
    ),
    "a skipped publish is never a boundary": (
        (GUARD, "        if False:\n"), {BOUNDARY},
    ),
    "a skipped publish is a boundary everywhere": (
        (GUARD, "        if _ship_at is None:\n"), {GIT_BOUNDARY},
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
    copy, evidence, foreign, profile = (Path(item).resolve() for item in argv[:4])
    whole = {"before": evidence / "before" / "validate.py", "foreign": foreign}
    env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    env.update(
        USERPROFILE=str(profile), HOME=str(profile), CLAUDE_CONFIG_DIR=str(profile / ".claude"),
        PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
    )
    target = copy / VALIDATE
    pristine = target.read_bytes()
    crlf = b"\r\n" in pristine
    problems = 0
    for name, (edit, expected) in MUTATIONS.items():
        try:
            if edit is not None:
                old, new = edit
                if old is None:
                    target.write_bytes(whole[new].read_bytes())
                else:
                    text = pristine.decode("utf-8").replace("\r\n", "\n")
                    if text.count(old) != 1:
                        raise RuntimeError(f"anchor not unique for {name!r}: {old.strip()!r}")
                    text = text.replace(old, new)
                    target.write_bytes(
                        (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
                    )
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
        print(f"{name}: ran {runs[0][1]}, red {sorted(reds[0])} -- {verdict}")
        if verdict != "as expected":
            print(f"    expected red: {sorted(expected)}; all: {[sorted(r) for r in reds]}")
    print(f"mutations: {len(MUTATIONS) - 1}, repetitions each: {REPEATS}, problems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
