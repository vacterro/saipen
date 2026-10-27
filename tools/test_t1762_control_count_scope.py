"""T-1762: the red half of a measured pair is evidence, not the checkpoint's claim.

The verify grammar asks an agent to measure a control pair and record both
halves. The honest record of one --

    verify -> PASS ... -- pre-fix 4 failed (red control), post-fix 0 failed

-- carries a counted failure shape, and `_claims_failure` honours that shape
from anywhere in the text, so `VERIFY -> REVIEW` and the finish refused a green
cycle for saying what it had measured (improve 20261013-1 IMP-004; SRC-248).
Same family as T-1444 (a foreign scope) and T-1620 (a previous run): a count
explicitly attributed elsewhere reports another state.

The scope, its vocabulary and its regex are the work of the session that
reported the finding from vacterro-saiwebsite. One thing was narrowed when it
landed here: the scope word keeps its separator. `prefix` is an ordinary word,
and a current count beside it is nobody's red control.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine.log import _claims_failure, verification_evidence  # noqa: E402
from test_verification_grammar import TICKET, events  # noqa: E402

#: The record the reporting project could not write (its T-33).
REPORTED = (
    "verify -> PASS [target: T-33] conf: high -- pre-fix 4 failed (red control), "
    "post-fix 0 failed"
)


class TheRecordTheGrammarAsksFor(unittest.TestCase):
    def test_the_reported_line_is_not_a_failure_claim(self) -> None:
        self.assertFalse(_claims_failure(REPORTED))

    def test_the_green_cycle_it_closes_is_accepted(self) -> None:
        ok, reason = verification_evidence(TICKET, events(REPORTED))
        self.assertTrue(ok, reason)
        self.assertEqual(reason, REPORTED)

    def test_an_attributed_red_half_never_claims(self) -> None:
        for text in (
            "PASS conf: high -- red control: 4 failed, post-fix green",
            "PASS conf: high -- pre-fix 3 failures, post-fix none",
            "PASS conf: high -- 4 failed (red control), then green on the fixed subject",
            "PASS conf: high -- the pre-fix run had 2 failures and the post-fix run is green",
            "PASS conf: high -- red-control 5 FAIL, the fixed subject 0 FAIL",
            "PASS conf: high -- pre fix baseline: 7 failed; after the fix all green",
        ):
            self.assertFalse(_claims_failure(text), text)


class ARealFailureIsNotTalkedPast(unittest.TestCase):
    def test_a_count_with_no_attribution_still_claims(self) -> None:
        for text in (
            "PASS conf: high -- 2 FAIL in the family",
            "PASS conf: high -- failures=2",
            "PASS conf: high -- the family ended with 3 failed",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_a_current_count_beside_the_control_still_claims(self) -> None:
        for text in (
            "PASS conf: high -- pre-fix 4 failed (red control), post-fix 2 failed",
            "PASS conf: high -- red control: 4 failed; and 1 failed on the fixed subject",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_a_failing_verdict_is_not_excused_by_its_control(self) -> None:
        text = "verify -> FAIL -- red control: 4 failed"
        self.assertTrue(_claims_failure(text))
        ok, _reason = verification_evidence(TICKET, events(text))
        self.assertFalse(ok)

    def test_the_ordinary_word_prefix_attributes_nothing(self) -> None:
        # The narrowing: these are current failures of tests ABOUT prefixes.
        for text in (
            "PASS conf: high -- 3 failed prefix tests remain",
            "PASS conf: high -- prefix 3 failed in the matcher suite",
            "PASS conf: high -- 2 failed (prefix matcher)",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_a_cycle_closed_over_a_prefix_count_is_refused(self) -> None:
        ok, _reason = verification_evidence(
            TICKET, events("verify -> PASS conf: high -- 3 failed prefix tests remain")
        )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
