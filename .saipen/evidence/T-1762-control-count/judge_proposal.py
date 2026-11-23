"""T-1762: judge the proposed control-count scope on a case table.

    python judge_proposal.py <tools-dir> [<tools-dir> ...]

Prints, per engine, what log._claims_failure answers for each line, beside
what a reader of the line would say. "must admit" lines state the red half of
a measured pair with an adjacent attribution; "must claim" lines carry a
failure that is the checkpoint's own. Reads and reports; it decides nothing.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ADMIT = (
    "verify -> PASS [target: T-33] conf: high -- pre-fix 4 failed (red control), post-fix 0 failed",
    "verify -> PASS conf: high -- red control: 4 failed, post-fix green",
    "verify -> PASS conf: high -- pre-fix 3 failures, post-fix none",
    "verify -> PASS conf: high -- 4 failed (red control), then green on the fixed subject",
    "review -> PASS conf: high -- the pre-fix run had 2 failures and the post-fix run is green",
)
CLAIM = (
    "verify -> PASS conf: high -- 2 FAIL in the family",
    "verify -> PASS conf: high -- failures=2",
    "verify -> FAIL -- red control: 4 failed",
    "verify -> PASS conf: high -- pre-fix 4 failed (red control), post-fix 2 failed",
    "verify -> PASS conf: high -- red control: 4 failed; and 1 failed on the fixed subject",
    # An ordinary word that the proposed vocabulary also spells: these are
    # current failures of tests ABOUT prefixes, attributed to no control.
    "verify -> PASS conf: high -- 3 failed prefix tests remain",
    "verify -> PASS conf: high -- prefix 3 failed in the matcher suite",
)


def answers(tools: Path) -> dict:
    for name in [key for key in sys.modules if key == "saipen_engine" or key.startswith("saipen_engine.")]:
        del sys.modules[name]
    sys.path.insert(0, str(tools))
    try:
        log = importlib.import_module("saipen_engine.log")
        return {line: log._claims_failure(line) for line in (*ADMIT, *CLAIM)}
    finally:
        sys.path.remove(str(tools))


def main(argv: list[str]) -> int:
    for item in argv:
        tools = Path(item).resolve()
        got = answers(tools)
        wrong_admit = [line for line in ADMIT if got[line]]
        wrong_claim = [line for line in CLAIM if not got[line]]
        print(f"== {tools}")
        for line in ADMIT:
            print(f"  must admit | reads as a claim: {got[line]!s:5} | {line[26:]}")
        for line in CLAIM:
            print(f"  must claim | reads as a claim: {got[line]!s:5} | {line[14:]}")
        print(f"  red halves still vetoed: {len(wrong_admit)}; current claims talked past: {len(wrong_claim)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
