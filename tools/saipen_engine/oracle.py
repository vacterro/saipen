"""Is this FAIL -> PASS pair evidence of a fix? (`VERIFY-ORACLE-01`)

`phases/verify.md` has always required a regression test that failed before the
fix. What it could not say was which test. Nothing bound the verifier that
produced the FAIL to the verifier that produced the PASS, so the cheapest way
to close a bug ticket was never to fix the bug:

    BUG EXISTS -> TEST FAILS -> weaken the fixture -> TEST PASSES -> DONE

Every downstream guard reads green. REVIEW re-runs the ticket's own `verify:`
and gets the same green from the same weakened oracle. `acceptance.py` marks
evidence stale only when BUILD is RE-entered, so an edit made inside the one
BUILD never trips it. The escaped-defect taxonomy already has the name for this
-- `CONTROL_DISARMED` -- and the instrument control is already the mechanism
against it. The only missing piece was arithmetic: hold the verifier fixed and
compare.

WHAT A DIGEST CAN AND CANNOT SAY. It can say the verifier changed, or did not.
It can never say the verifier is semantically correct: an oracle that asserts
the wrong behaviour hashes exactly as confidently as a right one. So identity
is half the contract and the red control in `phases/verify.md` is the other
half -- prove the same unchanged oracle goes RED against the PRE-FIX subject.
This module owns only the half a machine can decide.

Pure: it hashes bytes the caller names and compares records the caller built.
It reads no state, writes nothing, and knows nothing about tickets.
"""

from __future__ import annotations

import re
from pathlib import Path

from .journal import hash_bytes

RULE_ID = "VERIFY-ORACLE-01"

#: Verdicts. `ADMISSIBLE` is the only one that may be cited as fix evidence.
ADMISSIBLE = "ADMISSIBLE"
ORACLE_CHANGED = "ORACLE_CHANGED"
SUBJECT_UNCHANGED = "SUBJECT_UNCHANGED"
NOT_A_REGRESSION_PAIR = "NOT_A_REGRESSION_PAIR"

#: `oracle:<hex>` / `subject:<hex>` inside an evidence line. Optional by
#: design: a record without them is not rejected, it is simply unpairable, and
#: silently upgrading "no identity recorded" to "identity matched" would
#: manufacture exactly the confidence this exists to withhold.
_TOKEN = re.compile(r"\b(oracle|subject):([0-9a-f]{8,64})\b")

_MISSING = "(none)"


def oracle_digest(root: Path | str, paths) -> str:
    """Content identity of the files that DEFINE success for one check.

    The test, its fixtures, its golden files, its mocks -- whatever the caller
    names. An absent path contributes its name and an explicit absence marker
    rather than being skipped: deleting the failing case is one of the ways
    this defect is committed, and a deletion that changed nothing in the digest
    would be the one edit the check could not see.
    """
    root = Path(root)
    parts: list[str] = []
    for rel in sorted({str(p).replace("\\", "/") for p in (paths or ())}):
        target = root / rel
        try:
            body = hash_bytes(target.read_bytes()) if target.is_file() else _MISSING
        except OSError:
            body = _MISSING
        parts.append(f"{rel}={body}")
    return hash_bytes("\n".join(parts).encode("utf-8"))


def verifier_identity(command: str, oracle_paths=(), root: Path | str = ".") -> str:
    """What produced a verdict: the command plus the bytes that define success.

    The command belongs in the identity because narrowing test discovery,
    excluding a directory or swapping a behavioural run for a smoke run changes
    the question just as surely as editing an assertion does, and leaves every
    named file byte-identical.
    """
    return hash_bytes(
        "\n".join(
            [
                f"command={(command or '').strip()}",
                f"oracle={oracle_digest(root, oracle_paths)}",
            ]
        ).encode("utf-8")
    )


def parse_identity(text: str) -> dict:
    """The `oracle:` / `subject:` tokens carried by an evidence line, if any."""
    found = {}
    for key, value in _TOKEN.findall(text or ""):
        found[key] = value
    return found


def regression_pair_verdict(before: dict, after: dict) -> dict:
    """Does this FAIL -> PASS pair prove the SUBJECT is what changed?

    `before` and `after` are records carrying `result`, `verifier` and
    `subject`. The whole judgement is which of the two moved:

        verifier same,    subject changed -> ADMISSIBLE
        verifier changed, subject changed -> ORACLE_CHANGED, unattributable
        verifier changed, subject same    -> ORACLE_CHANGED, the greenwash
        verifier same,    subject same    -> SUBJECT_UNCHANGED, nothing to fix

    The second row matters as much as the third. Editing production code and
    its test in one pass leaves no way to prove which side turned the light
    green, and "probably the fix" is not evidence.
    """
    before = before or {}
    after = after or {}
    if str(before.get("result", "")).upper() != "FAIL" or str(
        after.get("result", "")
    ).upper() != "PASS":
        return _verdict(
            NOT_A_REGRESSION_PAIR,
            "a fix comparison is a FAIL against the pre-fix subject followed by a "
            f"PASS against the post-fix subject; got {before.get('result')!r} -> "
            f"{after.get('result')!r}",
        )

    before_v, after_v = before.get("verifier"), after.get("verifier")
    before_s, after_s = before.get("subject"), after.get("subject")
    if not before_v or not after_v:
        return _verdict(
            ORACLE_CHANGED,
            "no verifier identity was recorded for one side of the comparison, so "
            "the two runs cannot be shown to have asked the same question. An "
            "unrecorded identity is not a matching one",
        )
    if before_v != after_v:
        detail = (
            "the subject changed too, so nothing attributes the green to the fix "
            "rather than to the weaker check"
            if before_s and after_s and before_s != after_s
            else "the subject did not change, so the only thing that turned this "
            "green was the check itself"
        )
        return _verdict(
            ORACLE_CHANGED,
            f"the verifier changed between the FAIL and the PASS ({str(before_v)[:12]} "
            f"-> {str(after_v)[:12]}) -- {detail}. The earlier FAIL is not evidence "
            "for this fix; re-establish it against the current oracle",
        )
    if before_s and after_s and before_s == after_s:
        return _verdict(
            SUBJECT_UNCHANGED,
            "the same verifier reports FAIL then PASS against the same subject, "
            "which is an unstable verifier or an unrecorded change, never a proven "
            "fix",
        )
    return _verdict(
        ADMISSIBLE,
        "the same verifier failed against the pre-fix subject and passed against "
        "the post-fix subject, so the implementation is what changed",
    )


def _verdict(code: str, reason: str) -> dict:
    return {
        "code": code,
        "admissible": code == ADMISSIBLE,
        "reason": reason,
        "rule_id": RULE_ID,
    }
