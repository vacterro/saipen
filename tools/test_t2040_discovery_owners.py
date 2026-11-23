"""T-2040: discovery owners fail closed and preserve executable identity."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from saipen_engine import (
    automation, board, conformance, goal_authority, intake, persistent_goal,
    router, source_append, work_exhaustion as W,
)
from test_hermetic_env import isolate_host_session


def setUpModule():
    isolate_host_session()


class DiscoveryOwnerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-discovery-owner-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / ".saipen").mkdir()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for owner, name, result in (
            (goal_authority, "continuous_maintenance_proven", False),
            (intake, "active_receipts", []),
            (intake, "recover_orphans", {"ok": True, "orphans": []}),
            (intake, "verify_integrity", {"ok": True}),
            (intake, "coverage_complete", False),
            (source_append, "pending_appends", []),
            (source_append, "ledgers", []),
            (conformance, "conformance_status", {"status": conformance.STATUS_CURRENT_PASS}),
        ):
            self.stack.enter_context(mock.patch.object(owner, name, return_value=result))
        self.state = {"last_event": "generation-1", "agent": "tester"}

    def collect(self, tickets=None, **kwargs):
        return W.discovery_evidence(
            self.root, state=self.state, tickets=tickets or {},
            pending_ops=kwargs.pop("pending_ops", []),
            conflict_ops=kwargs.pop("conflict_ops", []), **kwargs,
        )

    def source(self, name, tickets=None, **kwargs):
        return self.collect(tickets, **kwargs)["source_evidence"][name]

    def unresolved(self, **meta):
        intake.active_receipts.return_value = [
            {"receipt": "SRC-001", "unresolved": 1, "linked_work": meta.get("linked_work")}
        ]
        self.stack.enter_context(mock.patch.object(intake, "_read_meta", return_value=meta))

    def test_recovery_ids_from_context_are_work_not_loader_failure(self):
        record = self.source(W.CANONICAL_RECOVERY, pending_ops=["op-1"])
        self.assertEqual(record["eligibility_result"], W.WORK_AVAILABLE, record)
        self.assertEqual(record["authorized_actions"], ["saipen recover"])

    def test_corrupt_recovery_cannot_be_checked_clean(self):
        record = self.source(W.CANONICAL_RECOVERY, pending_ops=[{"corrupt": True}])
        self.assertEqual(record["eligibility_result"], W.NOT_CHECKED)
        self.assertIn("corrupt", record["error"])

    def test_malformed_recovery_inventory_is_not_verified_empty(self):
        for value in ({}, "", [None]):
            with self.subTest(value=value):
                record = self.source(W.CANONICAL_RECOVERY, pending_ops=value)
                self.assertEqual(record["eligibility_result"], W.NOT_CHECKED, record)
                self.assertTrue(record["error"])

    def test_unworkable_linked_todo_is_not_source_work(self):
        self.unresolved(linked_work="T-2")
        tickets = board.parse_board(
            "## DOING\n## TODO\n- [ ] T-2 [P2] dependency | needs: T-1\n"
            "## DONE\n## BLOCKED\n- [ ] T-1 [P2] upstream | blocker: BLOCKED_EXTERNAL\n"
        )["tickets"]
        record = self.source(W.UNRESOLVED_SOURCE, tickets)
        self.assertEqual(record["eligibility_result"], W.BLOCKED_EXTERNAL, record)
        self.assertFalse(record["authorized_actions"])

    def test_authority_blocker_uses_canonical_fields(self):
        self.unresolved(linked_work="T-1")
        tickets = board.parse_board(
            "## DOING\n## TODO\n## DONE\n## BLOCKED\n"
            "- [ ] T-1 [P2] grant | blocker: BLOCKED_AUTHORITY_GATE: no grant\n"
        )["tickets"]
        self.assertEqual(
            self.source(W.UNRESOLVED_SOURCE, tickets)["eligibility_result"], W.BLOCKED_AUTHORITY,
        )

    def test_source_accounts_for_all_durable_work_members(self):
        self.unresolved(linked_work="T-1", linked_works=["T-2"])
        tickets = board.parse_board(
            "## DOING\n## TODO\n## DONE\n- [x] T-1 [P2] old work\n"
            "## BLOCKED\n- [ ] T-2 [P2] remaining | blocker: BLOCKED_EXTERNAL\n"
        )["tickets"]
        self.assertEqual(
            self.source(W.UNRESOLVED_SOURCE, tickets)["eligibility_result"], W.BLOCKED_EXTERNAL,
        )

    def test_missing_linked_work_is_incomplete_not_executable(self):
        self.unresolved(linked_work="T-999")
        record = self.source(W.UNRESOLVED_SOURCE)
        self.assertEqual(record["eligibility_result"], W.NOT_CHECKED, record)
        self.assertIn("T-999", record["error"])

    def test_unreadable_append_ledger_is_not_clean_source(self):
        source_append.ledgers.return_value = [{"source": "SRC-001", "error": "broken ledger"}]
        record = self.source(W.UNRESOLVED_SOURCE)
        self.assertEqual(record["eligibility_result"], W.NOT_CHECKED, record)
        self.assertIn("broken ledger", record["error"])

    def test_invalid_goal_loader_envelope_is_structured(self):
        with mock.patch.object(persistent_goal, "list_goals_report", return_value=None):
            evidence = self.collect()
        self.assertFalse(evidence["persistent_goals"]["complete"])
        self.assertTrue(evidence["persistent_goals"]["errors"])

    def test_missing_root_never_calls_discovery_owners(self):
        evidence = W.discovery_evidence(
            self.root / "missing", state=self.state, tickets={}, pending_ops=[], conflict_ops=[],
        )
        self.assertFalse(evidence["persistent_goals"]["root_available"])
        self.assertTrue(all(
            record["eligibility_result"] == W.NOT_CHECKED
            for record in evidence["source_evidence"].values()
        ))
        conformance.conformance_status.assert_not_called()
        intake.active_receipts.assert_not_called()

    def test_no_analysis_receipt_stays_not_checked(self):
        evidence = self.collect()
        for name in (W.HUNT_FINDINGS, W.IMPROVE_CANDIDATES, W.EXTERNAL_FORENSICS):
            self.assertEqual(evidence["source_evidence"][name]["eligibility_result"], W.NOT_CHECKED)

    def test_pure_router_does_not_load_goal_files(self):
        with mock.patch.object(persistent_goal, "list_goals_report", side_effect=AssertionError):
            result = board.classify_idle_work({}, persistent_goals=[])
        self.assertFalse(result["all_requirements_complete"])

    def test_outer_discovery_carrier_routes_active_work_without_hidden_reads(self):
        from test_campaign_continuation_assessment import _format_state

        evidence = self.collect(source_identity=mock.Mock(
            source_head="fixture-head", source_tree_fingerprint="fixture-tree",
        ))
        text = _format_state(phase="BUILD", task="T-1", next_action='"PHASE BUILD T-1"')
        board_text = "## DOING\n- [/] T-1 [P2] fixture\n## TODO\n## DONE\n## BLOCKED\n"
        with mock.patch.object(persistent_goal, "list_goals_report", side_effect=AssertionError):
            result = router.route_next(text, board_text, **evidence)
        self.assertEqual(result["reason"], "adopt", result)
        self.assertEqual(result["ticket"], "T-1", result)

    def test_source_generation_survives_router_and_idle_classification(self):
        from test_campaign_continuation_assessment import _format_state
        from test_fixture_support import checked_discovery_evidence

        generation = "fixture-head+fixture-tree"
        evidence = checked_discovery_evidence(generation)
        with mock.patch.object(persistent_goal, "list_goals_report", side_effect=AssertionError):
            result = router.route_next(
                _format_state(), "## DOING\n## TODO\n## DONE\n## BLOCKED\n",
                pending_ops=[], conflict_ops=[], persistent_goals=[],
                source_evidence=evidence, source_generation=generation,
            )
        certificate = result["work_exhaustion"]
        self.assertEqual(certificate["source_generation"], generation)
        # Caller-projected audit/future-gate rows stay unchecked, and an unproven
        # maintenance grant is an authority blocker: neither may read as quiescence.
        self.assertEqual(certificate["status"], W.INCOMPLETE_DISCOVERY, certificate)
        self.assertFalse(certificate["exhausted"])
        self.assertTrue(all(
            row["source_generation"] == generation for row in certificate["sources"]
        ), certificate)

    def test_bounded_discovery_hint_is_preserved_but_never_proves_exhaustion(self):
        from test_campaign_continuation_assessment import _format_state
        from test_fixture_support import checked_discovery_evidence

        generation = "fixture-head+fixture-tree"
        evidence = checked_discovery_evidence(generation)
        evidence[W.HUNT_FINDINGS] = {
            "source_generation": generation, "last_checked_generation": None,
            "eligibility_result": W.NOT_CHECKED, "checked": False,
            "authorized_actions": ["saipen hunt"],
        }
        hint = {"source_name": W.HUNT_FINDINGS, "source_generation": generation,
                "action": "saipen hunt", "bounded": True}
        result = router.route_next(
            _format_state(), "## DOING\n## TODO\n## DONE\n## BLOCKED\n",
            pending_ops=[], conflict_ops=[], persistent_goals=[], source_evidence=evidence,
            source_generation=generation, discovery_dispatch=hint,
        )
        certificate = result["work_exhaustion"]
        self.assertEqual(W.discovery_dispatch_for(certificate), hint, certificate)
        self.assertFalse(certificate["exhausted"])
        self.assertFalse(certificate["all_checked"])
        self.assertEqual(certificate["status"], W.INCOMPLETE_DISCOVERY)

    def test_missing_future_index_over_empty_corpus_is_checked_absence(self):
        from test_fixture_support import checked_discovery_evidence

        generation = "fixture-head+fixture-tree"
        certificate = W.certify_work_exhaustion(
            None, tickets={}, state={}, audit_inbox={"unresolved_audit_count": 0},
            future_gate={"index_state": "MISSING", "documents": 0,
                         "refresh_required": False, "eligible": [], "refinable": [],
                         "counts": {}},
            persistent_goals=[], source_evidence=checked_discovery_evidence(generation),
            source_generation=generation, continuous_maintenance_authorized=True,
        )
        row = next(item for item in certificate["sources"]
                   if item["source_name"] == W.FUTURE_GATES)
        self.assertTrue(row["checked"], row)
        self.assertEqual(row["eligibility_result"], W.CLEAN_VERIFIED, row)
        self.assertEqual(certificate["status"], W.VERIFIED_QUIESCENT, certificate)

    def test_owner_publication_proof_discharges_only_published_rows(self):
        from test_fixture_support import checked_discovery_evidence

        generation = "fixture-head+fixture-tree"
        tickets = board.parse_board(
            "## DOING\n## TODO\n## DONE\n"
            "- [x] T-1 [P2] shipped | publication_state: pending\n## BLOCKED\n"
        )["tickets"]
        owner = {"checked": True, "tickets": [
            {"ticket_id": "T-1", "status": "published",
             "receipt_ids": ["op-fixture"], "reason": "fixture owner proof"},
        ]}
        with mock.patch(
            "saipen_engine.outcome_truth.aggregate_publication_evidence",
            return_value=owner,
        ):
            certificate = W.certify_work_exhaustion(
                None, tickets=tickets, state={},
                audit_inbox={"unresolved_audit_count": 0},
                future_gate={"index_state": "CURRENT", "documents": 0,
                             "refresh_required": False, "eligible": [], "refinable": [],
                             "counts": {}},
                persistent_goals=[], source_evidence=checked_discovery_evidence(generation),
                source_generation=generation, continuous_maintenance_authorized=True,
                publication_evidence=object(),
            )
        row = next(item for item in certificate["sources"]
                   if item["source_name"] == W.RELEASE_OBLIGATIONS)
        self.assertEqual(row["eligibility_result"], W.CLEAN_VERIFIED, row)
        self.assertTrue(row["checked"], row)

    def test_unverified_publication_carrier_never_discharges_release_debt(self):
        from test_fixture_support import checked_discovery_evidence

        generation = "fixture-head+fixture-tree"
        tickets = board.parse_board(
            "## DOING\n## TODO\n## DONE\n"
            "- [x] T-1 [P2] shipped | publication_state: pending\n## BLOCKED\n"
        )["tickets"]
        with mock.patch(
            "saipen_engine.outcome_truth.aggregate_publication_evidence",
            return_value={"checked": False, "tickets": [],
                          "diagnostics": ["carrier is not owner-issued"]},
        ):
            certificate = W.certify_work_exhaustion(
                None, tickets=tickets, state={},
                audit_inbox={"unresolved_audit_count": 0},
                future_gate={"index_state": "CURRENT", "documents": 0,
                             "refresh_required": False, "eligible": [], "refinable": [],
                             "counts": {}},
                persistent_goals=[], source_evidence=checked_discovery_evidence(generation),
                source_generation=generation, continuous_maintenance_authorized=True,
                publication_evidence=object(),
            )
        row = next(item for item in certificate["sources"]
                   if item["source_name"] == W.RELEASE_OBLIGATIONS)
        self.assertEqual(row["eligibility_result"], W.BLOCKED_EXTERNAL, row)
        self.assertIn("T-1", row["exact_blocker"])

    def test_goal_completion_verdict_accepts_owner_publication_carrier(self):
        result = goal_authority.goal_completion_verdict(
            {}, {}, publication_evidence=object(), source_generation="generation-1",
        )
        self.assertIn("work_exhaustion", result, result)
        self.assertFalse(result["all_requirements_complete"], result)

    def test_forged_queue_shape_is_not_checked_absence(self):
        for tickets in ([], {"T-1": None}):
            with self.subTest(tickets=tickets):
                cert = W.certify_work_exhaustion(None, tickets=tickets)
                self.assertFalse(cert["all_checked"])
                self.assertTrue(cert["certificate_errors"])

    def test_supplied_empty_mapping_is_not_an_action_list(self):
        record = {
            "source_generation": "generation-1", "last_checked_generation": "generation-1",
            "eligibility_result": W.CLEAN_VERIFIED, "authorized_actions": {},
        }
        cert = W.certify_work_exhaustion(
            None, source_generation="generation-1", source_evidence={W.CONFORMANCE_DEBT: record},
        )
        source = next(row for row in cert["sources"] if row["source_name"] == W.CONFORMANCE_DEBT)
        self.assertEqual(source["eligibility_result"], W.NOT_CHECKED)

    def test_automation_cannot_override_incomplete_discovery_with_convergence(self):
        routed = {"ok": True, "reason": "maintain", "action": "saipen status",
                  "terminal_classification": W.INCOMPLETE_DISCOVERY,
                  "work_exhaustion": {"schema_version": 2, "status": W.INCOMPLETE_DISCOVERY}}
        with mock.patch.object(automation, "closure_gate", return_value={
            "complete": True, "convergence_current": True, "conditions": {},
        }):
            result = automation.automation_block(
                self.root, state={}, board={"tickets": {}}, routed=routed,
                audit_status={"ok": True, "layers": [], "orphans": [], "residue": []},
                convergence={"ok": True}, source_identity=mock.Mock(
                    source_head="head", source_tree_fingerprint="tree",
                ),
            )
        self.assertNotEqual(result["disposition"], automation.COMPLETE, result)
        self.assertFalse(result["closure_complete"])
        self.assertIsNone(result["next_command"])


if __name__ == "__main__":
    unittest.main()
