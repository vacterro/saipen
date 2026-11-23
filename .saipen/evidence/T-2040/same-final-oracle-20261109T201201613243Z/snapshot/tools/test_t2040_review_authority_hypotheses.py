"""T-2040: observation is not authority; malformed collect evidence fails closed.

Disposable projects and the existing simulated native-event broker only.
Run: python -B tools/test_t2040_review_authority_hypotheses.py
"""
from __future__ import annotations

import copy
import json
import unittest

from saipen_engine import (
    entry, goal_authority, intake, operations, persistent_goal, replenishment, subs,
)
from test_hermetic_env import isolate_host_session
import test_sub_dispose_after_collect as review_fixture
import test_t2023_goal_management_and_maintenance_binding as authority_fixture
import test_t2040_maintenance_authority as maintenance_fixture


def setUpModule():
    isolate_host_session()


class MaintenanceObservationTests(unittest.TestCase):
    def fixture(self, *, grant=True, revoke=False):
        root = authority_fixture._project(self, objective=authority_fixture.MAINTENANCE_OBJECTIVE)
        goal = authority_fixture._register_maintenance(
            root, evidence_provider="evidence_gap_ledger")
        goal.research_or_work_backlog_source = ".saipen/evidence/coverage_gap.json"
        persistent_goal.save_goal(root, goal)
        path = root / goal.research_or_work_backlog_source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"total": 1, "resolved": 0, "gaps": [{
            "id": "repair-1", "name": "Local parser",
            "verify": "The exact local regression oracle passes",
        }]}), encoding="utf-8")
        maintenance_fixture.block(self, root, "T-1", "BLOCKED_EXTERNAL -- foreign publication")
        if grant:
            proposal = goal_authority.propose_capsule(
                root, maintenance_fixture.current(root), authority_fixture._read_history(root))
            self.assertTrue(proposal["ok"], proposal)
            applied = authority_fixture._witnessed_apply(
                self, root, proposal["capsule_text"], revoke_after=revoke)
            self.assertTrue(applied.ok, applied.to_dict())
        return root, goal

    def test_native_admission_preserves_grant_identity_and_restart(self):
        root, goal = self.fixture()
        before = maintenance_fixture.current(root)
        digest = goal_authority.maintenance_goal_digest(goal)
        self.assertEqual(goal_authority.prove(root, before), [])
        result = replenishment.replenish_from_goals(root, "fix")
        self.assertTrue(result.get("replenished"), result)
        observed = persistent_goal.get_goal(root, goal.goal_id)
        self.assertEqual(observed.current_status, persistent_goal.STATUS_ACTIONABLE_GAPS)
        self.assertEqual(goal_authority.maintenance_goal_digest(observed), digest)
        after = maintenance_fixture.current(root)
        for key in goal_authority.FIELDS:
            self.assertEqual(after.get(key), before.get(key), key)
        self.assertEqual(goal_authority.prove(root, after), [])
        self.assertTrue(replenishment.maintenance_authority(root)["authorized"])
        frozen = maintenance_fixture.snapshot(root)
        self.assertEqual(
            replenishment.replenish_from_goals(root, "fix")["status"], "TODO_AVAILABLE")
        self.assertEqual(maintenance_fixture.snapshot(root), frozen)

    def test_observation_statuses_do_not_revoke_an_unchanged_grant(self):
        root, goal = self.fixture()
        digest = goal_authority.maintenance_goal_digest(goal)
        for status in sorted(persistent_goal.GOAL_STATUSES):
            with self.subTest(status=status):
                goal.current_status = status
                persistent_goal.save_goal(root, goal)
                self.assertEqual(goal_authority.maintenance_goal_digest(goal), digest)
                self.assertEqual(goal_authority.prove(root, maintenance_fixture.current(root)), [])
                self.assertIsNotNone(goal_authority.is_protected_goal_request(root, goal.objective))

    def test_policy_change_and_pause_still_refuse(self):
        root, goal = self.fixture()
        original = copy.deepcopy(goal)
        for field, value in (("success_criteria", {"required": "new policy"}),
                             ("admission_policy", {"scope": "new scope"}),
                             ("research_or_work_backlog_source", "other.json"),
                             ("paused", True)):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed.current_status = persistent_goal.STATUS_ACTIONABLE_GAPS
                setattr(changed, field, value)
                persistent_goal.save_goal(root, changed)
                self.assertTrue(goal_authority.prove(root, maintenance_fixture.current(root)))
                frozen = maintenance_fixture.snapshot(root)
                result = replenishment.replenish_from_goals(root, "fix")
                self.assertFalse(result.get("replenished"), result)
                self.assertEqual(maintenance_fixture.snapshot(root), frozen)

    def test_ungranted_or_revoked_observation_never_admits(self):
        for grant in (False, True):
            with self.subTest(revoked=grant):
                root, goal = self.fixture(grant=grant, revoke=grant)
                goal.current_status = persistent_goal.STATUS_ACTIONABLE_GAPS
                persistent_goal.save_goal(root, goal)
                frozen = maintenance_fixture.snapshot(root)
                self.assertFalse(replenishment.maintenance_authority(root)["authorized"])
                self.assertFalse(replenishment.replenish_from_goals(root, "fix").get("replenished"))
                self.assertEqual(maintenance_fixture.snapshot(root), frozen)

    def test_malformed_goal_inventory_never_binds_authority(self):
        root, goal = self.fixture()
        path = root / f".saipen/goals/{goal.goal_id}.json"
        for status in ("unknown", [], {}, None, 1):
            with self.subTest(status=status):
                raw = goal.to_dict()
                raw["current_status"] = status
                path.write_text(json.dumps(raw), encoding="utf-8")
                self.assertTrue(goal_authority.prove(root, maintenance_fixture.current(root)))

    def test_malformed_inventory_refuses_ingress_without_losing_request_or_seat(self):
        text = "Repair the local parser without changing maintenance authority"
        for command in ("user_request", "start"):
            with self.subTest(command=command):
                root = authority_fixture._project(
                    self, objective=authority_fixture.MAINTENANCE_OBJECTIVE)
                goal = authority_fixture._register_maintenance(root)
                raw = goal.to_dict()
                raw["current_status"] = []
                (root / f".saipen/goals/{goal.goal_id}.json").write_text(
                    json.dumps(raw), encoding="utf-8")
                before = maintenance_fixture.current(root)
                board = (root / ".saipen/BOARD.md").read_bytes()

                def request():
                    if command == "user_request":
                        return operations.user_request(root, "fix", text).to_dict()
                    return entry.start_work(root, "fix", actor_source="test", text=text)

                result = request()
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["code"], "GOAL_INVENTORY_UNAVAILABLE", result)
                refusal = result.get("refusal") or result
                self.assertNotIn("unregistered_code", refusal)
                receipt = result["receipt"]
                captured = intake.read_body(root, receipt)
                self.assertTrue(captured["ok"], captured)
                self.assertIn(text, captured["body"])
                self.assertEqual(
                    captured["meta"]["request_provenance"]["witness"], "model_supplied")
                self.assertFalse(captured["meta"].get("linked_work"))
                self.assertEqual((root / ".saipen/BOARD.md").read_bytes(), board)
                after = maintenance_fixture.current(root)
                for key in ("task", "phase", "agent", "next_action", *goal_authority.FIELDS):
                    self.assertEqual(after.get(key), before.get(key), key)
                frozen = maintenance_fixture.snapshot(root)
                replay = request()
                self.assertEqual(replay["code"], result["code"], replay)
                self.assertEqual(replay["receipt"], receipt)
                self.assertEqual(maintenance_fixture.snapshot(root), frozen)


class CollectHypothesisTests(unittest.TestCase):
    def setUp(self):
        self.fixture = review_fixture.CoreReviewProofTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.fixture._review()
        self.metadata = copy.deepcopy(self.fixture.records[0]["receipt_metadata"])
        self.hypothesis = {
            "producer": review_fixture.ROLE,
            "package_id": self.fixture.package.package_id,
            "source_head": review_fixture.AGED_HEAD,
            "source_tree_fingerprint": review_fixture.AGED_FINGERPRINT,
            "role_revision": review_fixture.FIXTURE_ROLE_REVISION,
        }

    def proof(self, hypotheses):
        f = self.fixture
        f.records[0]["receipt_metadata"] = {**self.metadata, "hypotheses": hypotheses}
        return subs._independent_core_review(f.root, f.package, f.ticket, f.collect_op,
                                              tuple(f.records))

    def test_valid_and_absent_legacy_hypotheses_still_bind(self):
        self.assertIsNotNone(self.proof([self.hypothesis])[0])
        f = self.fixture
        f.records[0]["receipt_metadata"] = self.metadata
        self.assertIsNotNone(subs._independent_core_review(
            f.root, f.package, f.ticket, f.collect_op, tuple(f.records))[0])

    def test_nested_null_numeric_and_missing_values_are_invalid(self):
        for key in self.hypothesis:
            for value in ([], {}, None, 7, False, ""):
                with self.subTest(key=key, value=value):
                    proof, problem = self.proof([{**self.hypothesis, key: value}])
                    self.assertIsNone(proof)
                    self.assertTrue(problem)
            missing = dict(self.hypothesis)
            missing.pop(key)
            self.assertIsNone(self.proof([missing])[0])
        proof, problem = self.proof([self.hypothesis, {"producer": []}])
        self.assertIsNone(proof)
        self.assertTrue(problem)

    def test_duplicate_and_contradictory_generations_fail_closed(self):
        for hypotheses in ([self.hypothesis, dict(reversed(list(self.hypothesis.items())))],
                           [{**self.hypothesis, "source_head": "d" * 40}],
                           [self.hypothesis, {**self.hypothesis, "note": []}]):
            with self.subTest(hypotheses=hypotheses):
                proof, problem = self.proof(hypotheses)
                self.assertIsNone(proof)
                self.assertTrue(problem)
        self.fixture.records[0]["status"] = "RESOLVED"
        self.assertIsNone(self.proof([self.hypothesis])[0])


if __name__ == "__main__":
    unittest.main()
