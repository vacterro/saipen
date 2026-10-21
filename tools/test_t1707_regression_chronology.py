"""A newer regression failure cannot spend an earlier success (T-1707)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.oracle import regression_evidence_verdict  # noqa: E402
from test_regression_gate import (  # noqa: E402
    GREEN,
    S1,
    S2,
    V1,
    RegressionGateFixture,
    _evidence,
    _ship_project,
)
from saipen_engine.operations import checkpoint, finish_ticket  # noqa: E402


class RegressionChronologyTests(unittest.TestCase):
    def verdict(self, *records):
        return regression_evidence_verdict([
            {"result": result, "verifier": verifier, "subject": subject}
            for result, verifier, subject in records
        ])

    def test_pass_before_fail_is_not_a_fix_comparison(self):
        answer = self.verdict(("PASS", V1, S2), ("FAIL", V1, S1))
        self.assertFalse(answer["admissible"], answer)

    def test_new_failure_invalidates_the_earlier_completed_pair(self):
        answer = self.verdict(("FAIL", V1, S1), ("PASS", V1, S2), ("FAIL", V1, S1))
        self.assertFalse(answer["admissible"], answer)

    def test_fresh_pass_after_the_latest_failure_remains_admissible(self):
        answer = self.verdict(
            ("FAIL", V1, S1), ("PASS", V1, S2), ("FAIL", V1, S1), ("PASS", V1, S2),
        )
        self.assertTrue(answer["admissible"], answer)

    def test_missing_half_keeps_its_existing_refusal(self):
        self.assertEqual(self.verdict(("FAIL", V1, S1))["code"], "NO_REGRESSION_EVIDENCE")


class CurrentGateChronologyTests(RegressionGateFixture):
    def test_active_verify_refuses_a_pass_older_than_the_latest_failure(self):
        self.record(_evidence("PASS", V1, S2))
        self.record(_evidence("FAIL", V1, S1))
        self.record(GREEN)  # ordinary PASS is a separate channel, not a regression PASS
        before = self.canonical_digest()
        answer = self.to_review()
        self.assertFalse(answer.ok, answer.to_dict())
        self.assertEqual(self.canonical_digest(), before)

    def test_active_verify_accepts_the_fresh_repair_after_that_failure(self):
        self.record(_evidence("PASS", V1, S2))
        self.record(_evidence("FAIL", V1, S1))
        self.record(_evidence("PASS", V1, S2))
        self.record(GREEN)
        answer = self.to_review()
        self.assertTrue(answer.ok, answer.to_dict())


class FinishChronologyTests(unittest.TestCase):
    def prepare(self, *, fresh_pass=False):
        project = _ship_project(self, pair=True)
        self.assertTrue(checkpoint(
            project, "tester", "RUN", "T-7", _evidence("FAIL", V1, S1),
        ).ok)
        if fresh_pass:
            self.assertTrue(checkpoint(
                project, "tester", "RUN", "T-7", _evidence("PASS", V1, S2),
            ).ok)
        self.assertTrue(checkpoint(project, "tester", "RUN", "T-7", GREEN).ok)
        return project

    def test_finish_refuses_the_pair_invalidated_by_a_new_failure(self):
        project = self.prepare()
        canonical = tuple(project / ".saipen" / name for name in (
            "STATE.md", "BOARD.md", "LOG.md",
        ))
        before = [path.read_bytes() for path in canonical]
        answer = finish_ticket(project, "T-7", "tester")
        self.assertFalse(answer.ok, answer.to_dict())
        self.assertIn("NOT_A_REGRESSION_PAIR", answer.message)
        self.assertEqual([path.read_bytes() for path in canonical], before)

    def test_finish_retains_the_existing_fresh_pair_behavior(self):
        project = self.prepare(fresh_pass=True)
        answer = finish_ticket(project, "T-7", "tester")
        self.assertTrue(answer.ok, answer.to_dict())


if __name__ == "__main__":
    unittest.main()
