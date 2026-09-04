"""Verification evidence grammar (T-1241).

Negative evidence has to win -- a real failure must never be talked past by a
cheerful summary in the same line. But the old rule was `"FAIL" in txt`, and
the canonical zero-failure summary every gate in this repository prints says
`validate.py --gate core 0 FAIL`. So the honest evidence line was rejected and
VERIFY could only reach REVIEW after someone wrote a second, weaker event that
avoided the word. This pins both halves: zero-count forms pass, any
unexplained failure token still fails, and the single-ticket and bulk
classifiers agree on every case.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine.log import (  # noqa: E402
    _claims_failure,
    bulk_verification_evidence,
    verification_evidence,
)

TICKET = "T-900"

CANONICAL = (
    "PASS conf: high -- validate.py --gate core 0 FAIL with 22 warnings; "
    "run_scenarios exit 0; audit_checks 227/227; ruff PASS"
)


def events(*texts: str) -> list[dict]:
    """A VERIFY boundary followed by the given RUN events, oldest first."""
    out = [{"taxonomy": "RUN", "ticket": TICKET, "text": "transition to VERIFY -- work done"}]
    for text in texts:
        out.append({"taxonomy": "RUN", "ticket": TICKET, "text": text})
    return out


class FailureClaims(unittest.TestCase):
    def test_zero_count_forms_are_not_failure_claims(self) -> None:
        for text in (
            "0 FAIL",
            "core gate 0 FAIL with 22 warnings",
            "no failures",
            "zero FAILURES",
            "0 failed",
            "validate.py --gate core 0 FAIL; ruff PASS",
        ):
            self.assertFalse(_claims_failure(text), text)

    def test_a_real_failure_count_still_claims_failure(self) -> None:
        for text in (
            "1 FAIL",
            "3 FAILED",
            "FAIL: source receipts",
            "the suite FAILED",
            "2 failures remain",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_a_mixed_line_counts_as_failure(self) -> None:
        # One gate green and another red is a failure, not a pass. The count
        # comparison exists precisely so a zero form cannot launder a real one.
        self.assertTrue(_claims_failure("core 0 FAIL, ship 3 FAIL"))

    def test_explicit_negation_still_wins(self) -> None:
        self.assertTrue(_claims_failure("NOT PASS"))
        self.assertTrue(_claims_failure("NOT MANUAL-VERIFY"))

    def test_text_without_the_token_is_not_a_claim(self) -> None:
        self.assertFalse(_claims_failure("PASS conf: high -- everything green"))
        self.assertFalse(_claims_failure(""))


class SingleTicket(unittest.TestCase):
    def test_the_canonical_zero_failure_summary_is_accepted(self) -> None:
        ok, reason = verification_evidence(TICKET, events(CANONICAL))
        self.assertTrue(ok, reason)

    def test_a_real_failure_is_still_rejected(self) -> None:
        ok, _ = verification_evidence(TICKET, events("PASS conf: high -- but 2 FAIL remain"))
        self.assertFalse(ok)

    def test_low_confidence_is_still_rejected(self) -> None:
        ok, _ = verification_evidence(TICKET, events("PASS conf: low -- 0 FAIL"))
        self.assertFalse(ok)

    def test_no_boundary_is_still_unproven(self) -> None:
        ok, reason = verification_evidence(
            TICKET, [{"taxonomy": "RUN", "ticket": TICKET, "text": CANONICAL}]
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "no current-cycle VERIFY boundary")

    def test_manual_verify_steps_are_not_a_human_verdict(self) -> None:
        """CORE-003. This test previously asserted the opposite, and that is
        why the defect survived: `MANUAL-VERIFY steps recorded; 0 FAIL` counted
        as successful verification.

        `phases/verify.md` REQUIRES an agent to record MANUAL-VERIFY STEPS +
        EXPECTED precisely when a human has NOT verified anything yet, so the
        instruction to wait for a person satisfied the gate that was waiting for
        that person. Steps are a request; only a recorded RESULT is a verdict.
        """
        ok, _ = verification_evidence(TICKET, events("MANUAL-VERIFY steps recorded; 0 FAIL"))
        self.assertFalse(ok)

    def test_prose_mentioning_the_token_is_not_a_human_verdict(self) -> None:
        """Narrative Authority Leakage, the class this module already names."""
        ok, _ = verification_evidence(
            TICKET, events("some prose that merely mentions MANUAL-VERIFY in passing")
        )
        self.assertFalse(ok)

    def test_a_recorded_human_pass_is_a_verdict(self) -> None:
        ok, _ = verification_evidence(
            TICKET, events("MANUAL-VERIFY RESULT: PASS -- operator confirmed the dialog")
        )
        self.assertTrue(ok)

    def test_a_recorded_human_fail_is_negative_evidence(self) -> None:
        ok, _ = verification_evidence(
            TICKET, events("MANUAL-VERIFY RESULT: FAIL -- operator reports a blank dialog")
        )
        self.assertFalse(ok)

    def test_the_result_marker_must_begin_the_event(self) -> None:
        """Anchoring is the whole property: a sentence CONTAINING it describes it."""
        ok, _ = verification_evidence(
            TICKET,
            events("we will later record MANUAL-VERIFY RESULT: PASS once someone looks"),
        )
        self.assertFalse(ok)


class ClassifierAgreement(unittest.TestCase):
    CASES = (
        CANONICAL,
        "PASS conf: high -- but 2 FAIL remain",
        "PASS conf: low -- 0 FAIL",
        "PASS conf: high",
        "MANUAL-VERIFY steps recorded; 0 FAIL",
        "NOT PASS",
        "core 0 FAIL, ship 3 FAIL",
        "nothing decisive here",
    )

    def test_bulk_and_single_agree_on_every_case(self) -> None:
        for text in self.CASES:
            history = events(text)
            single = verification_evidence(TICKET, history)
            bulk = bulk_verification_evidence(history, [TICKET])[TICKET]
            self.assertEqual(single, bulk, text)


if __name__ == "__main__":
    unittest.main()
