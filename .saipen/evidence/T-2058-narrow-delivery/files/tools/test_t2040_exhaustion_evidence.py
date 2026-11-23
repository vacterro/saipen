"""T-2040: positive discovery evidence, not a missing-work count, proves exhaustion."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import (
    board, continuation_assessment, outcome_truth, persistent_goal, router,
    work_exhaustion as W,
)
from test_hermetic_env import isolate_host_session
from test_t1807_audit_liveness_regression import _valid_state_text


def setUpModule() -> None:
    isolate_host_session()


class ExhaustionEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-t2040-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / ".saipen").mkdir()

    @staticmethod
    def checked(**overrides):
        inputs = {
            "tickets": {},
            "audit_inbox": {"pending": [], "unresolved_audit_count": 0},
            "future_gate": {"index_state": "CURRENT", "eligible": [], "counts": {}},
            "persistent_goals": [],
            "source_generation": "generation-1",
            "hunt_state": {"last_analyzed_generation": "generation-1", "findings": 0},
            "forensic_state": {"unfinished_slices": []},
            "continuous_maintenance_authorized": True,
            "source_evidence": {
                name: {
                    "source_generation": "generation-1",
                    "last_checked_generation": "generation-1",
                    "eligibility_result": W.CLEAN_VERIFIED,
                }
                for name in (W.CANONICAL_RECOVERY, W.UNRESOLVED_SOURCE,
                             W.CONFORMANCE_DEBT, W.IMPROVE_CANDIDATES)
            },
        }
        inputs.update(overrides)
        return inputs

    @staticmethod
    def source(cert, name):
        return next(row for row in cert["sources"] if row["source_name"] == name)

    def test_not_checked_cannot_certify_exhaustion(self):
        cert = W.certify_work_exhaustion(None)
        self.assertEqual(cert["status"], W.INCOMPLETE_DISCOVERY)
        self.assertFalse(cert["exhausted"])
        self.assertFalse(cert["all_checked"])

    def test_checked_absence_is_quiescent(self):
        cert = W.certify_work_exhaustion(None, **self.checked())
        self.assertEqual(cert["status"], W.VERIFIED_QUIESCENT)
        self.assertTrue(cert["exhausted"])
        self.assertTrue(cert["all_checked"])
        self.assertEqual({row["source_name"] for row in cert["sources"]}, set(W.ALL_WORK_SOURCES))

    def test_missing_root_is_not_a_readable_empty_inventory(self):
        cert = W.certify_work_exhaustion(self.root / "missing", **self.checked(persistent_goals=None))
        self.assertEqual(self.source(cert, W.PERSISTENT_GOALS)["eligibility_result"], W.NOT_CHECKED)
        self.assertFalse(cert["exhausted"])
        self.assertTrue(cert["certificate_errors"])

    def test_valid_goal_does_not_hide_failed_inventory_accounting(self):
        goal = persistent_goal.PersistentGoal("good", self.root.name, "Goal", "Repair defects")
        persistent_goal.save_goal(self.root, goal)
        (self.root / ".saipen/goals/broken.json").write_text("{", encoding="utf-8")
        cert = W.certify_work_exhaustion(self.root, **self.checked(persistent_goals=None))
        self.assertEqual(cert["status"], W.WORK_ELIGIBLE)
        self.assertFalse(cert["all_checked"])
        self.assertFalse(cert["exhausted"])
        self.assertTrue(cert["certificate_errors"])

    def test_waiting_goal_cannot_mask_independent_discovery(self):
        waiting = {"goal_id": "waiting", "current_status": "WAITING_AUTHORITY"}
        active = {"goal_id": "active", "current_status": "ACTIVE"}
        cert = W.certify_work_exhaustion(None, **self.checked(persistent_goals=[waiting, active]))
        self.assertEqual(cert["status"], W.WORK_ELIGIBLE)

    def test_authority_blocker_is_not_verified_quiescence(self):
        cert = W.certify_work_exhaustion(None, **self.checked(continuous_maintenance_authorized=False))
        self.assertEqual(cert["status"], W.BLOCKED_AUTHORITY)
        self.assertFalse(cert["exhausted"])

    def test_blocked_tickets_are_not_verified_absence(self):
        tickets = board.parse_board(
            "## DOING\n## TODO\n## DONE\n## BLOCKED\n"
            "- [ ] T-1 [P2] dependency | blocker: BLOCKED_EXTERNAL\n"
        )["tickets"]
        cert = W.certify_work_exhaustion(None, **self.checked(tickets=tickets))
        self.assertEqual(cert["status"], W.BLOCKED_EXTERNAL)
        self.assertFalse(cert["exhausted"])

    def test_dependency_blocked_todo_is_not_an_available_claim(self):
        tickets = board.parse_board(
            "## DOING\n## TODO\n- [ ] T-2 [P2] dependent | needs: T-1\n"
            "## DONE\n## BLOCKED\n- [ ] T-1 [P2] dependency | blocker: BLOCKED_EXTERNAL\n"
        )["tickets"]
        cert = W.certify_work_exhaustion(None, **self.checked(tickets=tickets))
        self.assertNotEqual(self.source(cert, W.ACTIONABLE_TODO)["eligibility_result"], W.WORK_AVAILABLE)

    def test_pending_publication_is_not_a_clean_release_inventory(self):
        tickets = {"T-1": {"id": "T-1", "section": "## DONE", "fields": {"publication_state": "pending"}}}
        cert = W.certify_work_exhaustion(None, **self.checked(tickets=tickets))
        self.assertNotEqual(self.source(cert, W.RELEASE_OBLIGATIONS)["eligibility_result"], W.CLEAN_VERIFIED)
        self.assertFalse(cert["exhausted"])

    def test_unworkable_audit_is_not_available_ingest(self):
        audit = {"unresolved_audit_count": 1, "unworkable_active_only": True,
                 "idle_classification": "IDLE_OPERATOR_REQUIRED"}
        cert = W.certify_work_exhaustion(None, **self.checked(audit_inbox=audit))
        self.assertEqual(self.source(cert, W.UNCONSUMED_AUDIT_INBOX)["eligibility_result"], W.BLOCKED_OPERATOR)

    def test_current_hunt_with_open_findings_is_not_unchanged(self):
        cert = W.certify_work_exhaustion(None, **self.checked(
            hunt_state={"last_analyzed_generation": "generation-1", "findings": 1}
        ))
        self.assertEqual(self.source(cert, W.HUNT_FINDINGS)["eligibility_result"], W.WORK_AVAILABLE)

    def test_active_goal_idle_result_also_carries_certificate(self):
        result = board.classify_idle_work({}, persistent_goals=[{"current_status": "ACTIVE"}])
        self.assertFalse(result["all_requirements_complete"])
        self.assertEqual(result["work_exhaustion"]["status"], W.WORK_ELIGIBLE)

    def test_router_never_reports_complete_over_unreadable_goal(self):
        (self.root / ".saipen/goals").mkdir()
        (self.root / ".saipen/goals/broken.json").write_text("{", encoding="utf-8")
        state = _valid_state_text()
        text = "## DOING\n## TODO\n## DONE\n## BLOCKED\n"
        with mock.patch.object(router, "queued_source_projection", return_value=None), mock.patch.object(
            router, "pending_append_projection", return_value=None
        ):
            result = router.route_next(
                state, text, project_root=self.root,
                **W.discovery_evidence(self.root, state={}, tickets={}),
            )
        self.assertNotEqual(result.get("terminal_classification"), "ALL_WORK_COMPLETE", result)
        self.assertIn("work_exhaustion", result)
        self.assertTrue(result["work_exhaustion"]["certificate_errors"])

    def test_legacy_exhausted_flag_does_not_prove_quiescence(self):
        truth = outcome_truth.compute_outcome_truth(
            None, tickets={}, has_continuous_maintenance=True,
            work_exhaustion={"exhausted": True},
        )
        self.assertNotEqual(truth["campaign_status"], outcome_truth.CAMPAIGN_QUIESCENT)

    def test_standalone_lane_cannot_certify_omitted_discovery(self):
        lanes = outcome_truth.compute_lane_statuses(None, tickets={}, has_continuous_maintenance=True)
        self.assertNotEqual(lanes["CAMPAIGN"], "QUIESCENT")

    def test_continuation_unknown_discovery_is_not_quiescent(self):
        route = {"ok": True, "reason": "maintain", "action": "saipen continue",
                 "terminal_classification": "INCOMPLETE_DISCOVERY"}
        with mock.patch.object(continuation_assessment.goal_authority, "continuous_maintenance_proven", return_value=False):
            result = continuation_assessment._classify_effective_route(
                self.root, route, route, {}, {"tickets": {}},
            )
        self.assertEqual(result["classification"], "INCOMPLETE_DISCOVERY")
        self.assertFalse(result["quiescent"])
        self.assertFalse(result["actionable"])

    def test_waiting_dependency_goal_is_not_runnable_discovery(self):
        result = board.classify_idle_work({}, persistent_goals=[
            {"goal_id": "waiting", "current_status": "WAITING_DEPENDENCY"}
        ])
        self.assertNotEqual(result["disposition"], "GOAL_GAPS_ACTIONABLE")
        self.assertFalse(result["all_requirements_complete"])

    def test_malformed_audit_count_remains_structured_unknown(self):
        result = board.classify_idle_work({}, audit_inbox={"pending": None})
        self.assertFalse(result["all_requirements_complete"])
        self.assertFalse(result["work_exhaustion"]["exhausted"])

    def test_report_needs_explicit_complete_observation(self):
        report = persistent_goal.goal_inventory({"goals": []})
        self.assertFalse(report["complete"])

    def test_paused_goal_does_not_prove_objective_satisfaction(self):
        inputs = self.checked(persistent_goals=[
            {"goal_id": "paused", "current_status": "ACTIVE", "paused": True}
        ])
        cert = W.certify_work_exhaustion(None, **inputs)
        self.assertTrue(cert["exhausted"])
        result = board.classify_idle_work(
            {}, persistent_goals=inputs["persistent_goals"], source_evidence=inputs["source_evidence"],
            audit_inbox=inputs["audit_inbox"], future_gate=inputs["future_gate"],
            state={"last_event": "generation-1"}, continuous_maintenance_authorized=True,
        )
        self.assertFalse(result["all_requirements_complete"])


if __name__ == "__main__":
    unittest.main()
