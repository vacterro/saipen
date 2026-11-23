"""T-1770 mutation controls, run in a disposable copy of the tree.

    python mutate1770.py <copy-root> <evidence-dir> <scratch-profile>

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
MODULE = "test_t1770_pair_stage_scope"
LOG = "tools/saipen_engine/log.py"

CITED = "test_the_cited_line_is_not_a_failure_claim"
CYCLE = "test_the_green_cycle_it_closes_is_accepted"
HALVES = "test_a_red_half_followed_by_its_green_twin_never_claims"
WORD = "test_before_without_the_red_half_shape_still_claims"
TWIN = "test_a_red_half_without_a_green_twin_still_claims"
BESIDE = "test_a_current_count_beside_a_pair_still_claims"

#: name -> (edit, tests that must go red). An edit is (old, new) inside log.py,
#: or (None, "before") for the whole pre-fix file.
MUTATIONS = {
    "control": (None, set()),
    "the engine before this Work": ((None, "before"), {CITED, CYCLE, HALVES}),
    "the scope is defined and never applied": (
        ('    scoped = _PAIR_RED_HALF_RE.sub(" ", scoped)\n', ""),
        {CITED, CYCLE, HALVES},
    ),
    "the word alone is the scope": (
        ('    r"\\bbefore" + _PAIR_EXIT + r"1\\b\\s*"\n',
         '    r"\\bbefore\\b[^/;]*?" + r"(?:exit\\s*1\\b)?\\s*"\n'),
        {WORD},
    ),
    "the green twin is not required": (
        ('    r"(?=\\s*[/;,]?\\s*(?:and\\s+|then\\s+)?after" + _PAIR_EXIT + r"0\\b)",\n',
         '    r"",\n'),
        {TWIN},
    ),
    "the twin's own counts join the half": (
        ('    r"(?=\\s*[/;,]?\\s*(?:and\\s+|then\\s+)?after" + _PAIR_EXIT + r"0\\b)",\n',
         '    r"\\s*[/;,]?\\s*(?:and\\s+|then\\s+)?after" + _PAIR_EXIT + r"0\\b[^;]*",\n'),
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
    copy, evidence, profile = (Path(item).resolve() for item in argv[:3])
    whole = {"before": evidence / "before" / "log.py"}
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
