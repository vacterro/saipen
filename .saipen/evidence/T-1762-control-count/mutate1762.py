"""T-1762 mutation controls, run in a disposable copy of the tree.

    python mutate1762.py <copy-root> <evidence-dir> <author-proposal-log.py> <scratch-profile>

Each mutation names the tests that must go red. The control and every mutation
run REPEATS times in fresh interpreters; a test red in some repetitions only is
reported as flaky. The copy is restored after each one.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPEATS = 3
MODULE = "test_t1762_control_count_scope"
LOG = "tools/saipen_engine/log.py"

REPORTED = "test_the_reported_line_is_not_a_failure_claim"
CYCLE = "test_the_green_cycle_it_closes_is_accepted"
HALVES = "test_an_attributed_red_half_never_claims"
BESIDE = "test_a_current_count_beside_the_control_still_claims"
PREFIX = "test_the_ordinary_word_prefix_attributes_nothing"
PREFIX_CYCLE = "test_a_cycle_closed_over_a_prefix_count_is_refused"

#: name -> (edit, tests that must go red). An edit is (old, new) inside log.py,
#: or (None, "before" | "author") for a whole-file replacement.
MUTATIONS = {
    "control": (None, set()),
    "the engine before this Work": ((None, "before"), {REPORTED, CYCLE, HALVES}),
    "the proposal as its author spelled it": ((None, "author"), {PREFIX, PREFIX_CYCLE}),
    "the scope is defined and never applied": (
        ("    scoped = _CONTROL_FAIL_RE.sub(\" \", scoped)\n", ""),
        {REPORTED, CYCLE, HALVES},
    ),
    "the fixed subject's own count joins the vocabulary": (
        ('_CONTROL_SCOPE = r"(?:red[- ]?controls?|pre[- ]fix)"\n',
         '_CONTROL_SCOPE = r"(?:red[- ]?controls?|pre[- ]fix|post[- ]fix)"\n'),
        {BESIDE},
    ),
}


def run_once(copy: Path, env: dict) -> tuple[set, int]:
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", MODULE, "-v"],
        cwd=copy / "tools", env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=600,
    )
    red = set(re.findall(r"^(?:FAIL|ERROR): (\w+) ", done.stderr, re.MULTILINE))
    ran = re.search(r"^Ran (\d+) test", done.stderr, re.MULTILINE)
    if ran is None:
        raise RuntimeError("no unittest summary:\n" + done.stderr[-1500:])
    return red, int(ran.group(1))


def main(argv: list[str]) -> int:
    copy, evidence, author, profile = (Path(item).resolve() for item in argv[:4])
    whole = {"before": evidence / "before" / "log.py", "author": author}
    env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    env.update(
        USERPROFILE=str(profile), HOME=str(profile), CLAUDE_CONFIG_DIR=str(profile / ".claude"),
        PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
    )
    target = copy / LOG
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
                        raise RuntimeError(f"anchor not unique for {name!r}: {old.strip()[:70]!r}")
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
        print(f"{name}: ran {runs[0][1]}, red {len(reds[0])} -- {verdict}")
        if verdict != "as expected":
            print(f"    expected: {sorted(expected)}")
            print(f"    got:      {[sorted(r) for r in reds]}")
    print(f"mutations: {len(MUTATIONS) - 1}, repetitions each: {REPEATS}, problems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
