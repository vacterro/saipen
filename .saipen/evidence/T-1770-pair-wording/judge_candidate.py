"""T-1770 SCOUT: judge a candidate pair-stage scope on a case table.

Read-only against the live engine: imports tools/saipen_engine/log.py and
applies the candidate substitution in front of `_claims_failure`, which is
where the shipped scope would sit (beside T-1444, T-1620 and T-1762). Prints
one row per case: the live verdict, the candidate verdict and the expected
candidate verdict.

Usage: python judge_candidate.py <project-root>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import log  # noqa: E402

_FAIL_WORD = r"FAIL(?:S|ED|URE|URES)?"
_OTHER_COUNT = r"\d+\s+(?:ran|passed|skipped)"
CANDIDATE = re.compile(
    r"\bbefore\s*:?\s*exit\s*(?:code\s*)?[:=]?\s*1\b\s*"
    r"(?:\(\s*(?:" + _OTHER_COUNT + r"\s*,\s*)*\d+\s+" + _FAIL_WORD + r"\b"
    r"(?:\s*,\s*" + _OTHER_COUNT + r")*\s*\)"
    r"|,\s*(?:" + _OTHER_COUNT + r"\s*,\s*)*\d+\s+" + _FAIL_WORD + r"\b)"
    r"(?=\s*[/;,]?\s*(?:and\s+|then\s+)?after\s*:?\s*exit\s*(?:code\s*)?[:=]?\s*0\b)",
    re.IGNORECASE,
)

E112 = (
    "verify -> PASS [target: T-8] conf: high -- python -m pytest -q from the repository "
    "root: 136 passed, 2 skipped, 0 failed, exit 0; plus the measured regression pair "
    "verifier e2d811aaef6be3befdd55753f446f21b9b08b89bd68d931fab3d010845ac6ded, before "
    "exit 1 (28 ran, 7 failed) / after exit 0 (28 passed); live CLI acceptance on an "
    "isolated store: tokenless same-id claim -> exit 3 LEASE_TOKEN_REQUIRED with the "
    "token unchanged, foreign checkpoint under a live lease -> exit 3 LEASE_HELD with "
    "head and capsule_count unmoved, holder write and release still succeed"
)

# (text, expected candidate verdict: True = still a failure claim)
CASES = [
    (E112, False),
    ("verify -> PASS conf: high -- before exit 1 (28 ran, 7 failed) / after exit 0 (28 passed)", False),
    ("PASS conf: high -- pair: before exit 1 (7 failed), after exit 0 (28 passed)", False),
    ("PASS conf: high -- before: exit 1 (28 ran, 7 failures); after: exit 0 (28 ran, 0 failed)", False),
    ("PASS conf: high -- before exit 1, 28 ran, 7 failed / after exit 0, 28 passed", False),
    ("PASS conf: high -- before exit 1 (7 failed, 21 passed) then after exit 0", False),
    # the word alone, or the pair without its green twin, attributes nothing
    ("PASS conf: high -- 3 failed before the retry, all green after", True),
    ("PASS conf: high -- before the fix 7 failed / after exit 0", True),
    ("PASS conf: high -- before exit 1 (28 ran, 7 failed)", True),
    ("PASS conf: high -- before exit 1 (28 ran, 7 failed); the family later", True),
    ("PASS conf: high -- before exit 1 (28 ran, 7 failed) / after exit 1 (28 ran, 2 failed)", True),
    ("PASS conf: high -- before exit 2 (7 failed) / after exit 0 (28 passed)", True),
    ("PASS conf: high -- 7 failed before exit 1 / after exit 0", True),
    # a current count beside a well-formed pair still claims
    ("PASS conf: high -- before exit 1 (7 failed) / after exit 0 (28 passed); family 2 failed", True),
    ("PASS conf: high -- before exit 1 (7 failed) / after exit 0 (28 ran, 3 failed)", True),
    ("PASS conf: high -- before exit 1 (7 failed) / after exit 0, and failures=1 in smoke", True),
    # the verdict keeps owning the current state
    ("verify -> FAIL -- before exit 1 (7 failed) / after exit 0 (28 passed)", True),
    ("NOT PASS -- before exit 1 (7 failed) / after exit 0 (28 passed)", True),
]


def candidate(text: str) -> bool:
    return log._claims_failure(CANDIDATE.sub(" ", text))


def main() -> int:
    problems = 0
    print("live  cand  want  | case")
    for text, want in CASES:
        live, cand = log._claims_failure(text), candidate(text)
        flag = "" if cand == want else "  <-- MISMATCH"
        problems += cand != want
        short = text if len(text) <= 110 else text[:107] + "..."
        print(f"{live!s:5} {cand!s:5} {want!s:5} | {short}{flag}")
    print(f"cases: {len(CASES)}, mismatches: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
