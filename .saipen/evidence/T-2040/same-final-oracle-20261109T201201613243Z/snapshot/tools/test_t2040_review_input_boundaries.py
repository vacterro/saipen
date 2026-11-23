"""T-2040: malformed or omitted owner evidence never proves checked absence."""

from __future__ import annotations

import unittest

import test_t2040_exhaustion_evidence as exhaustion_fixture
from saipen_engine import board, persistent_goal, work_exhaustion as W
from test_hermetic_env import isolate_host_session


def setUpModule():
    isolate_host_session()


class ReviewInputBoundaryTests(unittest.TestCase):
    def test_explicit_empty_future_inventory_still_verifies(self):
        cert = W.certify_work_exhaustion(None, **exhaustion_fixture.ExhaustionEvidenceTests.checked(
            future_gate={"index_state": "MISSING", "documents": 0,
                         "refresh_required": False, "eligible": [], "counts": {}},
        ))
        self.assertTrue(W.verified_quiescence(cert), cert)

    def test_invalid_state_with_explicit_actor_is_structured(self):
        for state in (["invalid"], "invalid", 1):
            with self.subTest(state=state):
                result = board.classify_idle_work({}, state=state, current_agent="reviewer")
                self.assertFalse(result["all_requirements_complete"])
                self.assertIn("state", result["work_exhaustion_error"])
                self.assertFalse(W.verified_quiescence(result["work_exhaustion"]))

    def test_unhashable_goal_status_is_incomplete_not_an_exception(self):
        for status in ([], {}, ["SATISFIED"]):
            with self.subTest(status=status):
                goals = [{"goal_id": "invalid", "current_status": status}]
                report = persistent_goal.goal_inventory(goals)
                self.assertFalse(report["complete"])
                self.assertTrue(report["errors"])
                result = board.classify_idle_work({}, persistent_goals=goals)
                self.assertFalse(result["all_requirements_complete"])
                self.assertFalse(W.verified_quiescence(result["work_exhaustion"]))

    def test_missing_future_inventory_fields_are_not_checked_empty(self):
        cases = [
            {"index_state": "MISSING"},
            {"index_state": "MISSING", "documents": 0},
            {"index_state": "MISSING", "refresh_required": False},
            *({"index_state": "MISSING", "documents": value, "refresh_required": False}
              for value in (None, False, "", {}, -1)),
            {"index_state": "MISSING", "documents": 0, "refresh_required": None},
        ]
        for future in cases:
            with self.subTest(future=future):
                cert = W.certify_work_exhaustion(
                    None, **exhaustion_fixture.ExhaustionEvidenceTests.checked(future_gate=future),
                )
                row = next(row for row in cert["sources"] if row["source_name"] == W.FUTURE_GATES)
                self.assertFalse(row["checked"], row)
                self.assertEqual(row["eligibility_result"], W.NOT_CHECKED)
                self.assertFalse(W.verified_quiescence(cert), cert)


if __name__ == "__main__":
    unittest.main()
