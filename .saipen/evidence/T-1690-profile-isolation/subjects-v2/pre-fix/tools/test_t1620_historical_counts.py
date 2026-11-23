"""T-1620 evidence semantics: a historical FAIL count must not veto a PASS.

A checkpoint narrates its history next to its verdict:

    PASS -- previous run: 5 failed / 23 passed; current run: 31 passed, 0 failed

The `5 failed` belongs to the previous run, but `_FAIL_COUNTED_RE` sees a
nonzero count before a FAIL-family token from anywhere and vetoes the clean
current PASS. The current verdict must take precedence over historical
narration -- while a genuine current count, bare or narrated, still blocks,
and ambiguous prose stays fail-safe.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine.log import _claims_failure  # noqa: E402


class HistoricalCountsAreNotClaims(unittest.TestCase):
    def test_the_ticket_example_is_not_a_failure_claim(self) -> None:
        self.assertFalse(
            _claims_failure(
                "PASS -- previous run: 5 failed / 23 passed; "
                "current run: 31 passed, 0 failed"
            )
        )

    def test_prior_and_last_run_attributions_are_not_claims(self) -> None:
        for text in (
            "verify -> PASS [target: T-1] conf: high -- prior run 2 failures, "
            "current run 31 passed, 0 failed",
            "PASS conf: high -- last attempt 1 FAIL, now 40 passed, 0 failed",
            "PASS -- 5 failed in the previous run; current run clean",
            "PASS -- earlier result showed 3 failures; now 12 passed, 0 failed",
        ):
            self.assertFalse(_claims_failure(text), text)


class CurrentCountsStillClaim(unittest.TestCase):
    def test_a_current_nonzero_count_beside_history_still_claims(self) -> None:
        for text in (
            "PASS -- previous run: 5 failed, current run: 2 failed",
            "PASS -- last run 0 failed, this run 3 failed",
            "PASS -- previous run clean, 2 failed now",
            "PASS conf: high -- but 2 FAIL remain",
            "2 failures remain",
            "5 failed",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_an_unattributed_bare_count_still_claims(self) -> None:
        # "the last 5 failed attempts" names no previous RUN, so the count
        # stays fail-safe: ambiguity blocks, it never passes.
        self.assertTrue(_claims_failure("PASS -- the last 5 failed attempts"))

    def test_no_constant_answer_satisfies_this_class(self) -> None:
        historical = _claims_failure(
            "PASS -- previous run: 5 failed; current run: 31 passed, 0 failed"
        )
        current = _claims_failure("PASS -- previous run clean, 2 failed now")
        self.assertFalse(historical)
        self.assertTrue(current)
        self.assertNotEqual(historical, current)


if __name__ == "__main__":
    unittest.main()
