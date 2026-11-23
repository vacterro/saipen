"""T-2040: incomplete discovery never becomes success or a human decision."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

import saipen as CLI
from campaign_test_support import inspect_fixture_campaign, write_scoped_fixture_grant
from saipen_engine import (
    automation, campaign, continuation_assessment as CA, continue_fallback,
    goal_authority, persistent_goal, router, supervisor, watchdog, worker,
    work_exhaustion as W,
)
from test_campaign_continuation_assessment import _format_state
from test_fixture_support import checked_discovery_evidence
from test_hermetic_env import isolate_host_session


BOARD = "## DOING\n## TODO\n## DONE\n## BLOCKED\n"


def setUpModule():
    isolate_host_session()


class ContinuationTruthTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-continuation-truth-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / ".saipen").mkdir()
        (self.root / ".saipen/STATE.md").write_text(_format_state(), encoding="utf-8")
        (self.root / ".saipen/BOARD.md").write_text(BOARD, encoding="utf-8")
        (self.root / ".saipen/LOG.md").write_text("# LOG\n", encoding="utf-8")
        (self.root / ".saipen/IDENTITY.md").write_text(
            "---\nproject_lineage: lineage-0123456789abcdef0123456789abcdef\n---\n",
            encoding="utf-8",
        )
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.certificate = {
            "schema_version": 2, "status": W.INCOMPLETE_DISCOVERY,
            "source_generation": "100", "sources": [], "all_checked": False,
            "exhausted": False, "certificate_errors": ["analysis not checked"],
        }
        self.routed = {
            "ok": True, "reason": "maintain", "action": "saipen continue",
            "terminal_classification": W.INCOMPLETE_DISCOVERY,
            "stop_reason": W.INCOMPLETE_DISCOVERY,
            "work_exhaustion": self.certificate,
            "work_exhaustion_error": "analysis not checked",
        }

    def admit_campaign(self):
        write_scoped_fixture_grant(self.root)
        self.stack.enter_context(mock.patch(
            "saipen_engine.host_authority_client.inspect_operator_campaign",
            side_effect=inspect_fixture_campaign,
        ))
        controller = campaign.CampaignController(self.root)
        admitted = controller.admit_campaign(
            campaign_id="CAMP-T2040-FIXTURE",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        self.assertTrue(admitted["admitted"], admitted)
        return controller

    @staticmethod
    def assessment(classification, action="saipen status"):
        return CA._make_assessment(
            classification, action=action, reason="fixture", detail="fixture evidence",
        )

    def fallthrough(self, **kwargs):
        payloads = []
        with mock.patch.object(CLI, "_emit", side_effect=lambda value, _: payloads.append(value)):
            rc = CLI._continue_improve_fallthrough(
                self.root, True, False, self.routed, [], [], None, **kwargs,
            )
        self.assertEqual(len(payloads), 1)
        return rc, payloads[0]

    def fallback_owners(self, *, marker=None):
        for owner, name, value in (
            (continue_fallback, "read_marker", marker or {}),
            (continue_fallback, "source_unchanged", (True, "fixture source unchanged")),
            (goal_authority, "continuous_maintenance_proven", True),
        ):
            self.stack.enter_context(mock.patch.object(owner, name, return_value=value))
        self.stack.enter_context(mock.patch.object(
            continue_fallback, "with_cycle_liveness", side_effect=lambda payload, _: payload,
        ))
        return self.stack.enter_context(mock.patch.object(CLI, "_public_improve"))

    def test_worker_evidence_gap_has_no_operator_action_or_generation(self):
        verdict = {
            "verdict": supervisor.INCOMPLETE_DISCOVERY, "reason": "analysis not checked",
            "next_command": "saipen status --json", "requires_human": False,
        }
        with mock.patch.object(watchdog, "observe", return_value=mock.Mock()), mock.patch.object(
            supervisor, "decide", return_value=verdict,
        ), mock.patch.object(worker, "take_authority") as take, mock.patch.object(
            worker, "_run_generation",
        ) as execute:
            result = worker._supervise(self.root, ["fixture-agent"], max_cycles=5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stop"], supervisor.INCOMPLETE_DISCOVERY)
        self.assertIsNone(result["operator_action"])
        self.assertEqual(result["counters"]["worker_generation_count"], 0)
        take.assert_not_called()
        execute.assert_not_called()

    def test_campaign_preserves_assessments_exact_discovery_action(self):
        controller = self.admit_campaign()
        action = "saipen future promote FG-1"
        with mock.patch.object(CA, "assess_continuation", return_value=self.assessment(
            CA.DISCOVERY_AVAILABLE, action,
        )):
            result = controller.step()
        self.assertEqual(result["event"], "DISCOVERY_AVAILABLE", result)
        self.assertEqual(result["state"]["next_action"], action)

    def test_campaign_restart_rechecks_evidence_without_operator_or_spin(self):
        controller = self.admit_campaign()
        with mock.patch.object(CA, "assess_continuation", return_value=self.assessment(
            CA.INCOMPLETE_DISCOVERY,
        )):
            first = controller.step()
        self.assertEqual(first["code"], CA.INCOMPLETE_DISCOVERY, first)
        self.assertEqual(first["state"]["campaign_state"], campaign.EXTERNAL_BLOCKED)
        self.assertEqual(first["state"]["worker_generation"], 0)

        restarted = campaign.CampaignController(self.root)
        action = "saipen future promote FG-1"
        with mock.patch.object(CA, "assess_continuation", return_value=self.assessment(
            CA.DISCOVERY_AVAILABLE, action,
        )) as assess:
            resumed = restarted.run(max_steps=1)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(len(resumed["steps"]), 1, resumed)
        self.assertEqual(resumed["steps"][0]["state"]["next_action"], action)
        assess.assert_called_once()

        state = campaign.inspect_campaign_state(self.root)["state"]
        state["campaign_state"] = campaign.EXTERNAL_BLOCKED
        campaign.save_campaign_state(self.root, state)
        with mock.patch.object(CA, "assess_continuation", return_value=self.assessment(
            CA.INCOMPLETE_DISCOVERY,
        )) as assess:
            stopped = restarted.run(max_steps=5)
        self.assertFalse(stopped["ok"], stopped)
        self.assertEqual(stopped["code"], CA.INCOMPLETE_DISCOVERY, stopped)
        self.assertNotIn("operator", stopped["reason"])
        assess.assert_called_once()

    def test_campaign_external_wait_does_not_require_operator(self):
        controller = self.admit_campaign()
        state = campaign.inspect_campaign_state(self.root)["state"]
        state["campaign_state"] = campaign.EXTERNAL_BLOCKED
        campaign.save_campaign_state(self.root, state)
        with mock.patch.object(CA, "assess_continuation", return_value=self.assessment(
            CA.WAIT_EXTERNAL,
        )) as assess:
            result = controller.run(max_steps=5)
        self.assertNotIn("requires_operator", result["reason"], result)
        self.assertEqual(len(result["steps"]), 1, result)
        assess.assert_called_once()

    def test_unchanged_source_and_valid_grant_do_not_prove_quiescence(self):
        improve = self.fallback_owners()
        rc, result = self.fallthrough()
        self.assertEqual(rc, 0)
        self.assertFalse(result["quiescent"], result)
        self.assertEqual(result["code"], W.INCOMPLETE_DISCOVERY)
        self.assertEqual(result["work_exhaustion"], self.certificate)
        improve.assert_not_called()

    def test_fallback_preserves_diagnostics_and_exact_stop_reason(self):
        self.fallback_owners(marker={"cycle_id": "fixture-active"})
        self.stack.enter_context(mock.patch.object(
            continue_fallback, "active_cycle_status", return_value="active",
        ))
        self.stack.enter_context(mock.patch.object(
            continue_fallback, "resume_action", return_value=("saipen improve status", "fixture"),
        ))
        _, result = self.fallthrough(chain_trace=[{"action": "fixture"}], iterations=1)
        self.assertEqual(result.get("work_exhaustion"), self.certificate)
        self.assertEqual(result.get("work_exhaustion_error"), "analysis not checked")
        self.assertEqual(result["stop_reason"], W.INCOMPLETE_DISCOVERY)

    def test_unreadable_goal_inventory_is_not_unchanged_success(self):
        improve = self.fallback_owners()
        goals = self.root / ".saipen/goals"
        goals.mkdir()
        (goals / "bad.json").write_text("{broken", encoding="utf-8")
        _, result = self.fallthrough()
        self.assertEqual(result["code"], W.INCOMPLETE_DISCOVERY, result)
        self.assertFalse(result["quiescent"])
        self.assertTrue(result["persistent_goals"]["errors"])
        improve.assert_not_called()

    def test_automation_uses_certificate_when_terminal_label_is_missing_or_false(self):
        for terminal in (None, "ALL_WORK_COMPLETE"):
            with self.subTest(terminal=terminal), mock.patch.object(
                automation, "closure_gate", return_value={
                    "complete": True, "convergence_current": True, "conditions": {},
                },
            ):
                routed = {**self.routed, "terminal_classification": terminal}
                result = automation.automation_block(
                    self.root, state={}, board={"tickets": {}}, routed=routed,
                    audit_status={"ok": True, "layers": [], "orphans": [], "residue": []},
                    convergence={"ok": True}, source_identity=mock.Mock(
                        source_head="head", source_tree_fingerprint="tree",
                    ),
                )
                self.assertEqual(result["disposition"], automation.BLOCKED, result)
                self.assertIsNone(result["next_command"])
                self.assertFalse(result["closure_complete"])

    def test_router_accepts_recovery_owner_ids_and_rejects_malformed_envelopes(self):
        text = _format_state()
        result = router.route_next(text, BOARD, pending_ops=[{"op_id": "op-fixture"}])
        self.assertEqual(result["reason"], "recovery-pending", result)
        self.assertIn("op-fixture", result["detail"])
        for inventory in ({}, "", [None], [{"corrupt": True}]):
            with self.subTest(inventory=inventory):
                result = router.route_next(text, BOARD, pending_ops=inventory, conflict_ops=[])
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["reason"], "recovery-invalid", result)
                self.assertEqual(result["action"], "saipen recover")

    def test_router_idle_classification_never_loads_goal_files(self):
        with mock.patch.object(
            persistent_goal, "list_goals_report", side_effect=AssertionError("hidden goal read"),
        ) as load:
            result = router.route_next(
                _format_state(), BOARD, pending_ops=[], conflict_ops=[], persistent_goals=[],
                source_evidence=checked_discovery_evidence("100"),
            )
        self.assertEqual(result["reason"], "maintain", result)
        load.assert_not_called()

    def test_assessment_reports_invalid_evidence_override_without_throwing(self):
        result = CA.assess_continuation(self.root, source_evidence=42)
        self.assertEqual(result["classification"], CA.INCOMPLETE_DISCOVERY, result)
        self.assertFalse(result["requires_human"])
        self.assertTrue(result["raw_route"]["work_exhaustion"]["certificate_errors"])


if __name__ == "__main__":
    unittest.main()
