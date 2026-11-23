"""T-2040: iteration preserves discovery uncertainty and exact execution routes."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import (
    continuation_assessment as CA, iteration, iteration_verdict as IV,
    supervisor, work_exhaustion as W,
)
from test_campaign_continuation_assessment import _format_state
from test_t2040_bounded_discovery_resume import incomplete_certificate
from test_t2040_terminal_consumer_guards import certificate, idle_route


class IterationTruthTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-iteration-truth-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / ".saipen").mkdir()
        (self.root / ".saipen/STATE.md").write_text(_format_state(), encoding="utf-8")
        (self.root / ".saipen/BOARD.md").write_text(
            "## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8",
        )
        (self.root / ".saipen/LOG.md").write_text("# LOG\n", encoding="utf-8")

    def verdict(self, cert, *, proven=False, classification=CA.INCOMPLETE_DISCOVERY):
        routed = idle_route(cert)
        assessment = CA._make_assessment(
            classification, action="saipen status", reason="maintain", detail="fixture observations",
            effective_route=routed, raw_route=routed, continuous_maintenance_proven=proven,
        )
        with mock.patch.object(CA, "assess_continuation", return_value=assessment), mock.patch.object(
            IV, "_recall_decision", return_value=None,
        ):
            return IV.project_iteration_verdict(self.root)

    def test_checked_terminal_control_retains_completion(self):
        cert = certificate()
        self.assertTrue(W.verified_quiescence(cert))
        result = self.verdict(cert, classification=CA.QUIESCENT)
        self.assertEqual(result["decision"], iteration.VALID_TERMINAL)
        self.assertTrue(IV.verdict_allows_goal_complete_ui(result))

    def test_unchecked_native_inventory_never_requests_a_human(self):
        result = IV.project_iteration_verdict(self.root)
        self.assertEqual(result["continuation_classification"], CA.INCOMPLETE_DISCOVERY, result)
        self.assertEqual(result["decision"], iteration.RUNTIME_PAUSED)
        self.assertFalse(result["requires_human"])
        self.assertFalse(result["goal_complete"])
        self.assertFalse(result["executable_action_remains"])

    def test_pure_unproven_terminal_is_runtime_pause_not_operator_wait(self):
        self.assertEqual(iteration.decide_turn(
            executor_compatible=True, goal_complete=False, executable_action_remains=False,
            operator_due=False, valve_tripped=False,
        ), iteration.RUNTIME_PAUSED)

    def test_valid_bounded_hint_remains_incomplete_but_resumes(self):
        cert = incomplete_certificate()
        before = copy.deepcopy(cert)
        result = self.verdict(cert, proven=True)
        self.assertEqual(result["decision"], iteration.AUTO_KICK, result)
        self.assertTrue(result["executable_action_remains"])
        self.assertEqual(result["route_action"], cert["discovery_dispatch"]["action"])
        self.assertEqual(result["continuation_classification"], CA.INCOMPLETE_DISCOVERY)
        self.assertFalse(result["requires_human"])
        self.assertFalse(result["goal_complete"])
        self.assertEqual(cert, before)

    def test_bad_or_unproven_hint_cannot_schedule(self):
        valid = incomplete_certificate()
        stale = copy.deepcopy(valid)
        stale["discovery_dispatch"]["source_generation"] = "stale"
        injected = copy.deepcopy(valid)
        injected["discovery_dispatch"]["action"] = "saipen release"
        for cert, proven in ((valid, False), (stale, True), (injected, True)):
            with self.subTest(certificate=cert, proven=proven):
                result = self.verdict(cert, proven=proven)
                self.assertEqual(result["decision"], iteration.RUNTIME_PAUSED, result)
                self.assertFalse(result["executable_action_remains"])
                self.assertFalse(result["requires_human"])

    def test_hint_never_overrides_real_authority_or_operator_boundary(self):
        for classification in (CA.WAIT_OPERATOR, CA.WAIT_AUTHORITY, CA.SAFETY_STOP):
            with self.subTest(classification=classification):
                result = self.verdict(incomplete_certificate(), proven=True, classification=classification)
                self.assertEqual(result["decision"], iteration.OPERATOR_WAIT)
                self.assertFalse(result["executable_action_remains"])
                self.assertTrue(result["requires_human"])

    def test_native_no_blocker_spellings_keep_bounded_discovery_available(self):
        from saipen_engine import goal_authority

        for blocker in ('""', "none"):
            with self.subTest(blocker=blocker):
                (self.root / ".saipen/STATE.md").write_text(_format_state(
                    blocker=blocker, continuation_authority="operator_persistent",
                    authority_until="continuous_maintenance", goal_ingress="goal-0123456789abcdef",
                ), encoding="utf-8")
                with mock.patch.object(goal_authority, "prove", return_value=[]):
                    assessment = CA.assess_continuation(self.root)
                    result = IV.project_iteration_verdict(self.root)
                self.assertEqual(assessment["classification"], CA.INCOMPLETE_DISCOVERY)
                self.assertEqual(assessment.get("action"), "saipen hunt")
                self.assertEqual(result["decision"], iteration.AUTO_KICK)
                self.assertFalse(result["goal_complete"])

    def test_foreign_external_ticket_cannot_hide_authorized_discovery(self):
        from saipen_engine import goal_authority

        (self.root / ".saipen/STATE.md").write_text(_format_state(
            blocker='""', continuation_authority="operator_persistent",
            authority_until="continuous_maintenance", goal_ingress="goal-0123456789abcdef",
        ), encoding="utf-8")
        (self.root / ".saipen/BOARD.md").write_text(
            "## DOING\n## TODO\n## DONE\n## BLOCKED\n"
            "- [ ] T-99 [P1] Foreign ticket | verify: external evidence | blocker: BLOCKED_EXTERNAL\n",
            encoding="utf-8",
        )
        with mock.patch.object(goal_authority, "prove", return_value=[]):
            assessment = CA.assess_continuation(self.root)
            result = IV.project_iteration_verdict(self.root)
            decision = supervisor.decide(self.root)
        self.assertEqual(assessment["classification"], CA.INCOMPLETE_DISCOVERY)
        self.assertEqual(assessment["action"], "saipen hunt")
        self.assertEqual(result["decision"], iteration.AUTO_KICK)
        self.assertEqual(decision["verdict"], supervisor.RUN_WORK)
        self.assertEqual(decision["work"], "saipen hunt")
        self.assertFalse(result["goal_complete"])

    def test_native_operator_stop_never_gets_a_discovery_hint(self):
        from saipen_engine import goal_authority

        (self.root / ".saipen/STATE.md").write_text(_format_state(
            blocker="WAIT_USER_DECISION", next_action='"WAIT: user brake -- retain stop"',
            continuation_authority="operator_persistent", authority_until="continuous_maintenance",
            goal_ingress="goal-0123456789abcdef",
        ), encoding="utf-8")
        with mock.patch.object(goal_authority, "prove", return_value=[]):
            assessment = CA.assess_continuation(self.root)
            result = IV.project_iteration_verdict(self.root)
        self.assertFalse(assessment.get("discovery_dispatch"))
        self.assertEqual(result["decision"], iteration.OPERATOR_WAIT)
        self.assertFalse(result["executable_action_remains"])

    def test_supervisor_queued_identity_does_not_lose_remediation_command(self):
        for classification, action, expected in (
            (CA.QUEUED_WORK, "PHASE SCOUT T-10", "T-10"),
            (CA.ACTIVE_WORK, "saipen work regression T-10 --file control.json",
             "saipen work regression T-10 --file control.json"),
        ):
            assessment = CA._make_assessment(
                classification, action=action, ticket="T-10", reason="fixture", detail="fixture",
            )
            with self.subTest(classification=classification), mock.patch.object(
                supervisor, "assess_continuation", return_value=assessment,
            ):
                result = supervisor.decide(self.root)
            self.assertEqual(result["verdict"], supervisor.RUN_WORK)
            self.assertEqual(result["work"], expected)
            self.assertEqual(result["observation"]["continuation_assessment"]["action"], action)


if __name__ == "__main__":
    unittest.main()
