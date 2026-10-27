"""T-1632: an identifier in front of FAIL is a citation, not a failure count.

Measured on T-1624: a verify checkpoint cited the red half of its regression
pair as

    verify -> PASS ... -- regression pair E-12503 FAIL / E-12504 PASS ...

and `VERIFY -> REVIEW` refused the green cycle. `_FAIL_COUNTED_RE` opened with a
word boundary, the hyphen of an event id is one, and `12503 FAIL` read as
12503 failures. Same family as T-1444 and T-1620: a citation is not a count.

Pinned both ways: digits that end an identifier (an event, ticket or receipt
id; an identity token behind its colon; a file:line) never claim, and a bare
nonzero count still claims from anywhere.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine.log import _claims_failure, verification_evidence  # noqa: E402
from test_verification_grammar import TICKET, events  # noqa: E402

#: The exact event text the gate refused (LOG E-12510).
E_12510 = (
    "verify -> PASS [target: T-1624] conf: high -- regression pair E-12503 FAIL / E-12504 "
    "PASS same verifier 7e7eb72e7be1564f ADMISSIBLE; incident controls A-F and concurrency "
    "9 OK; adversarial authority and broker and launch 57 OK; public install lifecycle 2 OK; "
    "adapter parity and runtime bootstrap 40 OK; host modules 101 OK; ruff clean; "
    "hostile-event probe 25 of 25 without a block; real Claude Code 2.1.291 on the final "
    "generation after host repair: tool call, new session and authority restart each "
    "ADMITTED under 300 ms, doctor HEALTHY_VERIFIED MECHANICAL (ACCEPTANCE.md section 5)"
)


class TheRefusedCheckpoint(unittest.TestCase):
    def test_the_exact_text_is_not_a_failure_claim(self) -> None:
        self.assertFalse(_claims_failure(E_12510))

    def test_the_green_cycle_it_closed_is_accepted(self) -> None:
        ok, reason = verification_evidence(TICKET, events(E_12510))
        self.assertTrue(ok, reason)
        self.assertEqual(reason, E_12510)


class AnIdentifierIsNotACount(unittest.TestCase):
    def test_ids_in_front_of_the_token_never_claim(self) -> None:
        for text in (
            "PASS conf: high -- regression pair E-12503 FAIL / E-12504 PASS",
            "PASS conf: high -- the red control is T-1241 FAIL by design, then green",
            "PASS conf: high -- SRC-166 FAILED its first reading and was re-read",
            "PASS conf: high -- gate FG-0046 failures are the ticket's own subject",
            "PASS conf: high -- cohort C-005 FAIL was the pre-fix half",
        ):
            self.assertFalse(_claims_failure(text), text)

    def test_identity_tokens_and_file_lines_never_claim(self) -> None:
        for text in (
            "PASS conf: high -- subject:12345678 FAIL before, subject:87654321 after",
            "PASS conf: high -- record sha256:1234567890 FAILED to match once, re-read",
            "PASS conf: high -- log.py:1278 FAIL family regex is what moved",
        ):
            self.assertFalse(_claims_failure(text), text)


class ABareCountStillClaims(unittest.TestCase):
    def test_a_bare_nonzero_count_claims_from_anywhere(self) -> None:
        for text in (
            "2 FAIL",
            "PASS conf: high -- but 2 FAIL remain",
            "PASS conf: high -- 12503 FAIL",
            "PASS conf: high -- (3 failed)",
            "PASS conf: high -- tests: 3 failed",
            "PASS conf: high -- 5 failed, 23 passed",
            "PASS conf: high -- suite A/2 failures",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_a_count_beside_a_citation_still_claims(self) -> None:
        self.assertTrue(
            _claims_failure("PASS conf: high -- pair E-12503 FAIL / E-12504 PASS; 2 FAIL remain")
        )

    def test_a_cited_id_does_not_launder_a_verdict_token(self) -> None:
        # The verdict segment keeps T-1241's rule: a FAIL token there claims,
        # whatever stands in front of it.
        self.assertTrue(_claims_failure("verify -> E-12503 FAIL [target: T-1]"))

    def test_no_constant_answer_satisfies_this_class(self) -> None:
        cited = _claims_failure("PASS conf: high -- pair E-12503 FAIL / E-12504 PASS")
        counted = _claims_failure("PASS conf: high -- 12503 FAIL")
        self.assertFalse(cited)
        self.assertTrue(counted)


if __name__ == "__main__":
    unittest.main()
