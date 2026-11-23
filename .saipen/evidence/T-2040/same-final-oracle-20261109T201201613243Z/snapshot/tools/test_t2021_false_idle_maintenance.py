"""Independent maintenance survives unrelated blockers without inventing authority."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import unittest
from unittest import mock

from saipen_engine import (
    automation,
    board,
    continue_loop,
    effects,
    goal_authority,
    replenishment,
    router,
)
from saipen_engine.discovery_providers import CandidateTask, ProviderEvaluation
from saipen_engine.persistent_goal import PersistentGoal, register_goal
from test_hermetic_env import isolate_host_session
from test_t1614_future_gate import _project


def setUpModule():
    isolate_host_session()


class IndependentMaintenanceTests(unittest.TestCase):
    def setUp(self):
        base, self.root = _project(intent="goal")
        self.addCleanup(shutil.rmtree, base, True)
        rows = [
            "- [ ] T-1 [P2] release fixture | blocker: "
            "PUBLICATION_STAGING_BLOCKED: 206 foreign paths"
        ] + [
            f"- [ ] T-{number} [P2] upstream fixture {number} | blocker: BLOCKED_EXTERNAL"
            for number in range(2, 101)
        ]
        self.board_text = "## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n" + "\n".join(rows) + "\n"
        (self.root / ".saipen/BOARD.md").write_text(self.board_text, encoding="utf-8")
        self.goal = PersistentGoal(
            "maintenance",
            self.root.name,
            "Maintain parser",
            "Repair verified parser defects",
            authorization_scope="MAINTENANCE",
            evidence_provider="test_provider",
        )
        register_goal(self.root, self.goal)
        self.audit = {
            "unworkable_active_only": True,
            "unresolved_audit_count": 1,
            "idle_classification": "IDLE_OPERATOR_REQUIRED",
            "action": "saipen audit status",
        }

    def evaluation(self):
        candidate = CandidateTask(
            "parser-gap-1",
            self.goal.goal_id,
            "Repair independent parser regression",
            verification="The independent parser fixture passes its regression oracle",
        )
        return ProviderEvaluation(
            "test_provider",
            "FAILED_TEST_DISCOVERY",
            "measured-generation-1",
            actionable_candidates=[candidate],
            candidate_ids=[candidate.candidate_id],
        )

    def test_active_goal_is_not_hidden_by_100_blocked_rows(self):
        tickets = board.parse_board(self.board_text)["tickets"]
        result = board.classify_idle_work(tickets, persistent_goals=[self.goal])
        self.assertEqual(result["disposition"], "GOAL_GAPS_ACTIONABLE")
        self.assertFalse(result["all_requirements_complete"])
        self.assertEqual(len(result["active_goals"]), 1)
        self.assertEqual(len(tickets), 100)

    def test_blocked_audit_does_not_hide_goal_discovery(self):
        state = (self.root / ".saipen/STATE.md").read_text(encoding="utf-8")
        result = router.route_next(
            state, self.board_text, project_root=self.root, audit_inbox=self.audit,
            persistent_goals=[self.goal],
        )
        self.assertEqual(result["reason"], "maintain")
        self.assertEqual(result["terminal_classification"], "GOAL_GAPS_ACTIONABLE")
        self.assertEqual(result["unresolved_audit_count"], 1)
        self.assertEqual(
            continue_loop.classify_route(
                result,
                {"execution_intent": "goal"},
                {"tickets": board.parse_board(self.board_text)["tickets"]},
            ),
            continue_loop.IDLE_MAINTAIN,
        )

    def test_maintenance_without_grant_cannot_admit_or_mutate(self):
        before = {path.name: path.read_bytes() for path in (self.root / ".saipen/goals").iterdir()}
        provider = mock.Mock()
        provider.evaluate.return_value = self.evaluation()
        with mock.patch.object(replenishment, "get_provider", return_value=provider), mock.patch(
            "saipen_engine.operations.ticket_add"
        ) as add:
            result = replenishment.replenish_from_goals(self.root, "tester")
        self.assertFalse(result["replenished"])
        self.assertEqual(result["status"], "WAITING_AUTHORITY")
        add.assert_not_called()
        self.assertEqual(
            (self.root / ".saipen/BOARD.md").read_text(encoding="utf-8"), self.board_text
        )
        self.assertEqual(
            before,
            {path.name: path.read_bytes() for path in (self.root / ".saipen/goals").iterdir()},
        )

    def test_proven_maintenance_grant_admits_independent_work_through_saioops(self):
        provider = mock.Mock()
        provider.evaluate.return_value = self.evaluation()
        with mock.patch.object(
            replenishment, "get_provider", return_value=provider
        ), mock.patch.object(
            goal_authority, "continuous_maintenance_proven", return_value=True
        ) as proof:
            result = replenishment.replenish_from_goals(self.root, "tester")
        self.assertTrue(result["replenished"], result)
        proof.assert_called_once()
        current = board.parse_board((self.root / ".saipen/BOARD.md").read_text(encoding="utf-8"))
        self.assertEqual(current["tickets"][result["admitted_ticket"]]["section"], "## TODO")
        self.assertEqual(
            sum(row["section"] == "## BLOCKED" for row in current["tickets"].values()), 100
        )

    def test_an_unavailable_provider_is_an_explicit_evidence_limit(self):
        provider = mock.Mock()
        provider.evaluate.side_effect = RuntimeError("provider unavailable")
        with mock.patch.object(replenishment, "get_provider", return_value=provider):
            results = replenishment.evaluate_all_goals(self.root)
        evaluation = results[0][1]
        self.assertEqual(evaluation.satisfaction_status, "BLOCKED_BY_EVIDENCE")
        self.assertEqual(evaluation.completeness_status, "UNKNOWN")
        self.assertIn("provider unavailable", " ".join(evaluation.blockers))

    def test_waiting_goal_cannot_mask_an_independent_actionable_goal(self):
        waiting = {
            **self.goal.to_dict(),
            "goal_id": "release",
            "current_status": "WAITING_AUTHORITY",
        }
        result = board.classify_idle_work(
            board.parse_board(self.board_text)["tickets"], persistent_goals=[waiting, self.goal]
        )
        self.assertEqual(result["disposition"], "GOAL_GAPS_ACTIONABLE")

    def test_paused_goals_do_not_supply_continuation_authority(self):
        self.goal.paused = True
        result = board.classify_idle_work(
            board.parse_board(self.board_text)["tickets"], persistent_goals=[self.goal]
        )
        self.assertNotEqual(result["disposition"], "ALL_WORK_COMPLETE")
        self.assertNotIn("active_goals", result)

    def test_a_waiting_todo_dependency_cannot_mask_independent_work(self):
        text = self.board_text.replace(
            "## TODO\n", "## TODO\n- [ ] T-101 [P2] dependent fixture | needs: T-1\n"
        )
        (self.root / ".saipen/BOARD.md").write_text(text, encoding="utf-8")
        provider = mock.Mock()
        provider.evaluate.return_value = self.evaluation()
        with mock.patch.object(
            replenishment, "get_provider", return_value=provider
        ), mock.patch.object(goal_authority, "continuous_maintenance_proven", return_value=True):
            result = replenishment.replenish_from_goals(self.root, "tester", dry_run=True)
        self.assertTrue(result["replenished"], result)

    def test_status_gate_names_maintenance_approval_instead_of_release_approval(self):
        route = {
            "ok": True,
            "action": "saipen continue",
            "reason": "maintain",
            "stop_reason": "NO_ADMISSIBLE_WORK",
            "active_goals": [self.goal.to_dict()],
        }
        result = router.continuous_maintenance_gate(self.root, route)
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "goal-waiting-authority")
        self.assertIn("saipen goal authorize", result["operator_action"])
        self.assertNotIn("release", result["operator_action"].lower())
        disposition, reason = automation._routing_disposition(
            result, result["action"], result["reason"]
        )
        self.assertEqual((disposition, reason), ("WAIT_USER", "goal-waiting-authority"))

    def test_status_gate_permits_a_proven_standing_maintenance_grant(self):
        route = {
            "ok": True,
            "action": "saipen continue",
            "reason": "maintain",
            "stop_reason": "NO_ADMISSIBLE_WORK",
            "active_goals": [self.goal.to_dict()],
        }
        with mock.patch.object(goal_authority, "continuous_maintenance_proven", return_value=True):
            self.assertIsNone(router.continuous_maintenance_gate(self.root, route))

    def test_release_candidate_cannot_starve_authorized_local_maintenance(self):
        release = PersistentGoal(
            "release",
            self.root.name,
            "Publish",
            "Publish reviewed work",
            authorization_scope="RELEASE",
            evidence_provider="release_provider",
        )
        register_goal(self.root, release)
        release_candidate = CandidateTask("publish", "release", "Publish fixture", priority="P0")
        release_evaluation = ProviderEvaluation(
            "release_provider",
            "RELEASE_GAP_DISCOVERY",
            "release-generation",
            actionable_candidates=[release_candidate],
        )
        maintenance = mock.Mock()
        maintenance.evaluate.return_value = self.evaluation()
        publication = mock.Mock()
        publication.evaluate.return_value = release_evaluation
        with mock.patch.object(
            replenishment,
            "get_provider",
            side_effect=lambda name: publication if name == "release_provider" else maintenance,
        ), mock.patch.object(goal_authority, "continuous_maintenance_proven", return_value=True):
            result = replenishment.replenish_from_goals(self.root, "tester", dry_run=True)
        self.assertTrue(result["replenished"], result)
        self.assertEqual(result["goal_id"], "maintenance")

    def test_goal_waiting_authority_has_a_waiting_status_gate(self):
        route = {
            "ok": True,
            "action": "saipen continue",
            "reason": "maintain",
            "stop_reason": "WAITING_AUTHORITY",
            "active_goals": [self.goal.to_dict()],
        }
        result = router.continuous_maintenance_gate(self.root, route)
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "goal-waiting-authority")

    def test_persisted_status_does_not_stall_a_goal_with_new_valid_authority(self):
        from saipen_engine.persistent_goal import save_goal

        self.goal.current_status = "WAITING_AUTHORITY"
        save_goal(self.root, self.goal)
        state = (self.root / ".saipen/STATE.md").read_text(encoding="utf-8")
        state = state.replace('next_action: "saipen continue"', 'next_action: "saipen status"')
        route = router.route_next(
            state, self.board_text, project_root=self.root, persistent_goals=[self.goal],
        )
        self.assertEqual(route["action"], "saipen continue")
        with mock.patch.object(goal_authority, "continuous_maintenance_proven", return_value=True):
            self.assertIsNone(router.continuous_maintenance_gate(self.root, route))
        self.assertEqual(
            continue_loop.classify_route(route, {"execution_intent": "goal"}, {"tickets": {}}),
            continue_loop.IDLE_MAINTAIN,
        )

    def test_unverified_scope_label_cannot_admit_work(self):
        self.goal.authorization_scope = "UNLIMITED"
        from saipen_engine.persistent_goal import save_goal

        save_goal(self.root, self.goal)
        provider = mock.Mock()
        provider.evaluate.return_value = self.evaluation()
        with mock.patch.object(replenishment, "get_provider", return_value=provider), mock.patch(
            "saipen_engine.operations.ticket_add"
        ) as add:
            result = replenishment.replenish_from_goals(self.root, "tester")
        self.assertFalse(result["replenished"])
        self.assertEqual(result["status"], "WAITING_AUTHORITY")
        add.assert_not_called()

    def test_dependent_candidate_cannot_starve_independent_candidate(self):
        evaluation = self.evaluation()
        dependent = CandidateTask(
            "blocked-parser",
            self.goal.goal_id,
            "Blocked parser change",
            priority="P0",
            needs=["T-1"],
        )
        evaluation.actionable_candidates.insert(0, dependent)
        provider = mock.Mock()
        provider.evaluate.return_value = evaluation
        with mock.patch.object(
            replenishment, "get_provider", return_value=provider
        ), mock.patch.object(goal_authority, "continuous_maintenance_proven", return_value=True):
            result = replenishment.replenish_from_goals(self.root, "tester", dry_run=True)
        self.assertTrue(result["replenished"], result)
        self.assertEqual(result["candidate"]["candidate_id"], "parser-gap-1")

    def test_unknown_provider_is_an_evidence_gap_not_a_satisfied_goal(self):
        with mock.patch.object(replenishment, "get_provider", return_value=None):
            evaluations = replenishment.evaluate_all_goals(self.root)
        _, evaluation = evaluations[0]
        self.assertEqual(evaluation.satisfaction_status, "BLOCKED_BY_EVIDENCE")
        self.assertEqual(evaluation.completeness_status, "UNKNOWN")
        self.assertIn("test_provider", evaluation.blockers[0])

    def test_live_ambiguous_ownership_is_not_historical_foreign_staging(self):
        blocker = board.project_blockers(board.parse_board(self.board_text)["tickets"])["groups"][0]
        inventory = {
            "verification_status": "VERIFIED_COMPLETE",
            "entries": [{}] * 3,
            "classification_summary": {"AMBIGUOUS_PROVENANCE": 3},
        }
        with mock.patch(
            "saipen_engine.isolated_release.inventory_staged_entries", return_value=inventory
        ):
            result = router.reconcile_publication_staging_blocker(self.root, blocker)
        self.assertIsNotNone(result)
        self.assertEqual(result["foreign_staged_count"], 0)
        self.assertEqual(result["ambiguous_staged_count"], 3)
        self.assertFalse(result["recovery_internally_authorized"])
        self.assertNotIn("206", result["root_cause"])

    def test_read_only_live_inventory_preserves_the_index(self):
        from saipen_engine.isolated_release import inventory_staged_entries

        for words in (["init", "-q"], ["add", "evidence.md"]):
            subprocess.run(["git", *words], cwd=self.root, capture_output=True, check=True)
        index = self.root / ".git/index"
        before = hashlib.sha256(index.read_bytes()).hexdigest()
        result = inventory_staged_entries(self.root)
        self.assertEqual(result["verification_status"], "VERIFIED_COMPLETE")
        self.assertEqual(hashlib.sha256(index.read_bytes()).hexdigest(), before)

    def test_read_only_discovery_preserves_the_untracked_cache_bytes(self):
        for words in (
            ["init", "-q"],
            ["config", "core.untrackedCache", "true"],
            ["add", "evidence.md"],
            ["status", "--porcelain"],
        ):
            subprocess.run(["git", *words], cwd=self.root, capture_output=True, check=True)
        (self.root / "new-evidence.md").write_text("new discovery input", encoding="utf-8")
        index = self.root / ".git/index"
        before = index.read_bytes()
        result = effects.tree_snapshot(self.root)
        self.assertEqual(result["status"], "KNOWN")
        self.assertIn("new-evidence.md", result["paths"])
        self.assertEqual(index.read_bytes(), before, "discovery must preserve UNTR cache too")

    def test_status_distribution_probe_preserves_index_stat_cache(self):
        import autoinject

        manifest = self.root / "saipen/MANIFEST.json"
        manifest.parent.mkdir()
        manifest.write_text(json.dumps({"files": [{"src": "evidence.md"}]}), encoding="utf-8")
        for words in (["init", "-q"], ["add", "evidence.md"]):
            subprocess.run(["git", *words], cwd=self.root, capture_output=True, check=True)
        path = self.root / "evidence.md"
        info = path.stat()
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 3_000_000_000))
        index = self.root / ".git/index"
        before = index.read_bytes()
        result = autoinject.injection_blockers(self.root)
        self.assertNotEqual(result["condition"], autoinject.BLOCK_NO_GIT)
        self.assertEqual(index.read_bytes(), before, "status must not refresh the index stat cache")


if __name__ == "__main__":
    unittest.main()
