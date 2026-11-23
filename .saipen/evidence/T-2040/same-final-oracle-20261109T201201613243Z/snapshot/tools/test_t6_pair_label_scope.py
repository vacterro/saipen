"""T-6 (SAI_LIBRARY improve imp-sai_library-20261105-1 IMP-001): the protocol's
own PAIR LABELS are not a failure claim.

The protocol mands the red half of a measured pair in words it owns: the SRC
acceptance line "All P1 findings fixed and independently reproduced RED ->
GREEN", the archive wording "Same-incident RED -> GREEN evidence exists", and
the mission's mandated RECORD FORMAT ("a NEGATIVE CONTROLS section and a
pre-fix/post-fix leg pair"). An agent that transcribes the pair that way --

    verify -> PASS [target: T-9] conf: high -- all P1 fixed:
    RED 52 ran 19 failed -> GREEN 52 ran 0 failed

-- could not close a green cycle, while the SAME measured fact spelled
`pre-fix 19 failed, post-fix 0 failed` was already exempt (T-1762). Three
spellings, one fact, two opposite verdicts: not the documented
fail-safe-on-ambiguity behaviour, but a fifth polarity of the narrative
authority leak T-1444, T-1620, T-1762 and T-1770 each cured.

Same cure, same discipline as T-1770: the scope is the whole RED half, and the
label word alone attributes nothing. A bare `RED 3 failed` with no green twin,
a count outside the labelled half, and the twin's own counts all still claim.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine.log import _claims_failure, verification_evidence  # noqa: E402
from test_verification_grammar import TICKET, events  # noqa: E402

#: The record the mission asks a report's NEGATIVE CONTROLS section to carry.
E_RED_GREEN = (
    "verify -> PASS [target: T-9] conf: high -- all 7 P1 findings fixed and "
    "independently reproduced RED -> GREEN: RED 52 ran 19 failed -> GREEN 52 ran "
    "0 failed, exit 1 before and exit 0 after; suite 52/52; gate core PASS"
)


class TheProtocolsOwnLabels(unittest.TestCase):
    def test_the_mandated_red_green_pair_is_not_a_failure_claim(self) -> None:
        self.assertFalse(_claims_failure(E_RED_GREEN))

    def test_the_green_cycle_it_closes_is_accepted(self) -> None:
        ok, reason = verification_evidence(TICKET, events(E_RED_GREEN))
        self.assertTrue(ok, reason)
        self.assertEqual(reason, E_RED_GREEN)

    def test_a_labelled_red_half_with_a_green_twin_never_claims(self) -> None:
        for text in (
            "PASS conf: high -- RED 19 failed -> GREEN 0 failed",
            "PASS conf: high -- RED 52 ran 19 failed -> GREEN 52 ran 0 failed",
            "PASS conf: high -- RED 19 failures -> GREEN 0 failures",
            "PASS conf: high -- RED: 19 failed -> GREEN 0 failed",
            "PASS conf: high -- RED 19 failed, GREEN 0 failed",
            "PASS conf: high -- RED 52 ran 19 failed; GREEN 52 ran 0 failed",
            "PASS conf: high -- pre-fix leg 19 failed, post-fix leg 0 failed",
            "PASS conf: high -- pre-fix leg 19 failed -> GREEN 0 failed",
            "PASS conf: high -- RED leg 19 failed then post-fix leg 0 failed",
        ):
            self.assertFalse(_claims_failure(text), text)


class TheLabelAloneAttributesNothing(unittest.TestCase):
    def test_red_without_a_green_twin_still_claims(self) -> None:
        for text in (
            "PASS conf: high -- RED 3 failed",
            "PASS conf: high -- RED 19 failed and the run never went green",
            "PASS conf: high -- pre-fix leg 3 failed",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_a_green_twin_that_is_not_reached_still_claims(self) -> None:
        for text in (
            "PASS conf: high -- RED 19 failed, worse 21 failed",
            "PASS conf: high -- GREEN 0 failed but RED 19 failed, and now 4 failed",
        ):
            self.assertTrue(_claims_failure(text), text)


class ACurrentCountIsNotTalkedPast(unittest.TestCase):
    def test_a_current_count_beside_a_pair_still_claims(self) -> None:
        for text in (
            "PASS conf: high -- RED 19 failed -> GREEN 0 failed then 3 failed",
            "PASS conf: high -- RED 19 failed -> GREEN 0 failed, smoke 2 failed",
            "PASS conf: high -- RED 19 failed -> GREEN 0 failed; failures=1 in unit",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_a_current_count_with_no_pair_still_claims(self) -> None:
        for text in (
            "verify -> PASS conf: high -- 19 failed, exit 0",
            "2 FAIL",
            "tests: 3 failed",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_a_failing_verdict_is_not_excused_by_its_pair(self) -> None:
        for text in (
            "verify -> FAIL -- RED 19 failed -> GREEN 0 failed",
            "NOT PASS -- RED 19 failed -> GREEN 0 failed",
        ):
            self.assertTrue(_claims_failure(text), text)
            ok, _reason = verification_evidence(TICKET, events(text))
            self.assertFalse(ok, text)


if __name__ == "__main__":
    unittest.main()
