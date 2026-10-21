"""T-1770: the red half of a measured pair, in the engine's own words, is no claim.

`saipen work regression` measures a pair in two stages and records each run's
`stage`, `exit_code`, `ran` and `failed`. An agent that transcribes that
receipt writes the red half as it reads it --

    before exit 1 (28 ran, 7 failed) / after exit 0 (28 passed)

-- and `_claims_failure` read the `7 failed` as the checkpoint's own claim, so
the verify line the operator's mission cites (SRC-248 R005; _sairelay T-8, its
E-112) could not close a green cycle, while the same line with the count left
out (its E-113) could. T-1762 attributes a count to `red control` and
`pre-fix`; this line attributes it to the receipt's `before` stage.

`before` is an ordinary word, so the word is not the scope: the scope is the
whole red half, `before exit 1` with its count, followed by its green twin
`after exit 0`. A count the line does not put inside that half still claims,
and so does a red half whose twin is not green.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine.log import _claims_failure, verification_evidence  # noqa: E402
from test_verification_grammar import TICKET, events  # noqa: E402

#: _sairelay .saipen/LOG.md, E-112, as recorded (T-8's verify checkpoint).
E112 = (
    "verify -> PASS [target: T-8] conf: high -- python -m pytest -q from the repository "
    "root: 136 passed, 2 skipped, 0 failed, exit 0; plus the measured regression pair "
    "verifier e2d811aaef6be3befdd55753f446f21b9b08b89bd68d931fab3d010845ac6ded, before "
    "exit 1 (28 ran, 7 failed) / after exit 0 (28 passed); live CLI acceptance on an "
    "isolated store: tokenless same-id claim -> exit 3 LEASE_TOKEN_REQUIRED with the "
    "token unchanged, foreign checkpoint under a live lease -> exit 3 LEASE_HELD with "
    "head and capsule_count unmoved, holder write and release still succeed"
)


class TheReceiptsOwnWords(unittest.TestCase):
    def test_the_cited_line_is_not_a_failure_claim(self) -> None:
        self.assertFalse(_claims_failure(E112))

    def test_the_green_cycle_it_closes_is_accepted(self) -> None:
        ok, reason = verification_evidence(TICKET, events(E112))
        self.assertTrue(ok, reason)
        self.assertEqual(reason, E112)

    def test_a_red_half_followed_by_its_green_twin_never_claims(self) -> None:
        for text in (
            "PASS conf: high -- before exit 1 (28 ran, 7 failed) / after exit 0 (28 passed)",
            "PASS conf: high -- pair: before exit 1 (7 failed), after exit 0 (28 passed)",
            "PASS conf: high -- before: exit 1 (28 ran, 7 failures); after: exit 0 (28 ran)",
            "PASS conf: high -- before exit 1, 28 ran, 7 failed / after exit 0, 28 passed",
            "PASS conf: high -- before exit 1 (7 failed, 21 passed) then after exit 0",
        ):
            self.assertFalse(_claims_failure(text), text)


class TheWordAloneAttributesNothing(unittest.TestCase):
    def test_before_without_the_red_half_shape_still_claims(self) -> None:
        for text in (
            "PASS conf: high -- 3 failed before the retry, all green after",
            "PASS conf: high -- before the fix 7 failed / after exit 0",
            "PASS conf: high -- 7 failed before exit 1 / after exit 0",
            "PASS conf: high -- before exit 2 (7 failed) / after exit 0 (28 passed)",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_a_red_half_without_a_green_twin_still_claims(self) -> None:
        for text in (
            "PASS conf: high -- before exit 1 (28 ran, 7 failed)",
            "PASS conf: high -- before exit 1 (28 ran, 7 failed); the family later",
            "PASS conf: high -- before exit 1 (28 ran, 7 failed) / after exit 1 (28 ran)",
        ):
            self.assertTrue(_claims_failure(text), text)


class ACurrentCountIsNotTalkedPast(unittest.TestCase):
    def test_a_current_count_beside_a_pair_still_claims(self) -> None:
        for text in (
            "PASS conf: high -- before exit 1 (7 failed) / after exit 0 (28 passed); "
            "family 2 failed",
            "PASS conf: high -- before exit 1 (7 failed) / after exit 0 (28 ran, 3 failed)",
            "PASS conf: high -- before exit 1 (7 failed) / after exit 0, failures=1 in smoke",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_a_current_count_with_no_pair_still_claims(self) -> None:
        self.assertTrue(_claims_failure("verify -> PASS conf: high -- 7 failed, exit 0"))

    def test_a_failing_verdict_is_not_excused_by_its_pair(self) -> None:
        for text in (
            "verify -> FAIL -- before exit 1 (7 failed) / after exit 0 (28 passed)",
            "NOT PASS -- before exit 1 (7 failed) / after exit 0 (28 passed)",
        ):
            self.assertTrue(_claims_failure(text), text)
            ok, _reason = verification_evidence(TICKET, events(text))
            self.assertFalse(ok, text)


if __name__ == "__main__":
    unittest.main()
