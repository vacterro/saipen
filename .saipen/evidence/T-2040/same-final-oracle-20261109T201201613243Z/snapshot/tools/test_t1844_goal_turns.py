"""An accepted goal survives a new genuine event in its same native session.

Native process identity is explicitly simulated by the existing isolated
broker fixture. These are no claims about actual host/UI acceptance.
"""

from __future__ import annotations

import copy
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from saipen_engine import goal_authority, operations, operator_task as OT
from saipen_engine import host_authority_client as HC
from saipen_engine.state import parse_state, patch_state
import test_t1844_origin_broker as controls
from test_hermetic_env import isolate_host_session


def setUpModule():
    isolate_host_session()


class NativeGoalTurns(unittest.TestCase):
    def setUp(self):
        self.origin = controls.OriginKernelWithSimulatedNativeIdentity()
        self.origin.setUp()
        self.addCleanup(self.origin.doCleanups)
        self.proof, self.state = self.origin.enter_goal()
        self.root = self.origin.root
        self.assertEqual(self.prove(), [], "known-good original native goal")

    def next_turn(self, *, action="report", text="Report the current progress",
                  session="session-A", model=None, provider=None):
        result = self.origin.broker.handle({
            "op": "issue-origin", "project": str(self.root), "session": session,
            "host": "claude", "event": "UserPromptSubmit", "request_text": text,
            "event_id": "next-turn", "action": action, "model": model, "provider": provider,
        }, self.origin.native_peer)
        self.assertTrue(result["ok"], result)
        proof = result["proof"]
        self.origin.register(proof, worker=40)
        self.origin.peer = SimpleNamespace(pid=40)
        return proof

    def prove(self):
        with mock.patch.object(HC, "_call", side_effect=self.origin.bridge):
            return goal_authority.prove(self.root, self.state)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def test_next_genuine_same_session_event_preserves_the_committed_goal_without_writes(self):
        self.next_turn()
        files = self.snapshot()
        records = copy.deepcopy(self.origin.broker.origins.records)
        self.assertEqual(self.prove(), [])
        self.assertEqual(self.snapshot(), files)
        self.assertEqual(self.origin.broker.origins.records, records)

    def test_same_session_continuation_survives_both_delivery_expiries(self):
        self.origin.now += 61
        self.next_turn()
        self.origin.now += 61
        self.assertEqual(self.prove(), [])
        with mock.patch.object(HC, "_call", side_effect=self.origin.bridge):
            authority = OT.authority_for_provenance({
                "witness": OT.WITNESS_CARRIER, "declared_by": OT.DECLARED_HOST_INGRESS,
                "compared_digest": self.proof["request_digest"], "operator_origin": self.proof,
            }, root=self.root)
        self.assertFalse(authority["goal_pivot"])
        self.assertFalse(authority["reset_bounded_authority"])

    def test_another_registered_session_cannot_borrow_the_goal(self):
        self.next_turn(session="session-B")
        self.assertTrue(self.prove())

    def test_a_revoked_next_event_does_not_delegate_the_goal(self):
        proof = self.next_turn()
        self.assertEqual(self.prove(), [])
        result = self.origin.broker.handle(
            {"op": "revoke-origin", "host": "claude", "proof": proof},
            self.origin.native_peer,
        )
        self.assertTrue(result["ok"], result)
        self.assertTrue(self.prove())
        self.origin.peer = self.origin.worker_peer
        self.assertEqual(self.prove(), [])

    def test_an_event_from_another_goal_epoch_is_not_session_membership(self):
        path = self.root / ".saipen/STATE.md"
        original = path.read_bytes()
        path.write_text(patch_state(original.decode(), {"goal_ingress": "goal-" + "f" * 16}),
                        encoding="utf-8")
        try:
            self.next_turn()
        finally:
            path.write_bytes(original)
        self.assertTrue(self.prove())

    def test_a_changed_model_cannot_use_the_old_goal_registration(self):
        self.next_turn(model="other-model")
        self.assertTrue(self.prove())

    def test_a_changed_provider_cannot_use_the_old_goal_registration(self):
        self.next_turn(provider="other-provider")
        self.assertTrue(self.prove())

    def test_a_different_budget_epoch_is_not_session_membership(self):
        path = self.root / ".saipen/STATE.md"
        original = path.read_bytes()
        path.write_text(patch_state(original.decode(), {"authority_source": "E-999"}),
                        encoding="utf-8")
        try:
            self.next_turn()
        finally:
            path.write_bytes(original)
        self.assertTrue(self.prove())

    def test_native_repeat_of_the_same_goal_is_a_zero_write_semantic_retry(self):
        proof = self.next_turn(action="goal", text=controls.TEXT)
        OT.admit_host_ingress({
            "request_text": controls.TEXT, "session_id": "session-A",
            "message_id": "next-turn", "operator_origin": proof,
        }, self.root)
        before = self.snapshot()
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), \
                mock.patch.object(HC, "_call", side_effect=self.origin.bridge):
            result = operations.goal_entry(self.root, "test-agent", controls.TEXT)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.code, "GOAL_ALREADY_CAPTURED")
        self.assertEqual(self.snapshot(), before)

    def test_native_new_objective_can_pivot_from_its_same_session_goal(self):
        text = "repair the new exact importer objective"
        proof = self.next_turn(action="goal", text=text)
        OT.admit_host_ingress({
            "request_text": text, "session_id": "session-A",
            "message_id": "next-turn", "operator_origin": proof,
        }, self.root)
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), \
                mock.patch.object(HC, "_call", side_effect=self.origin.bridge):
            result = operations.goal_entry(self.root, "test-agent", text)
            self.assertTrue(result.ok, result.to_dict())
            self.assertEqual(result.code, "GOAL_SET")
            state = parse_state((self.root / ".saipen/STATE.md").read_text())
            self.assertNotEqual(state["goal_ingress"], self.state["goal_ingress"])
            self.assertEqual(goal_authority.prove(self.root, state), [])
            self.assertTrue(goal_authority.prove(self.root, self.state))


class BoundBudgetEpoch(unittest.TestCase):
    def test_a_goal_source_cannot_reset_a_later_bounded_budget(self):
        origin = controls.OriginKernelWithSimulatedNativeIdentity()
        origin.setUp()
        self.addCleanup(origin.doCleanups)
        proof = origin.issue(action="goal")
        origin.register(proof)
        receipt = origin.bind_source(proof)
        with mock.patch.object(HC, "_call", side_effect=origin.bridge):
            before = OT.authority_for_receipt(origin.root, receipt)
            self.assertTrue(before["reset_bounded_authority"], before)
            origin.state("T-1", budget="E-2")
            records = copy.deepcopy(origin.broker.origins.records)
            after = OT.authority_for_receipt(origin.root, receipt)
            self.assertTrue(after["user_explicit"], "accepted Source origin remains attributable")
            self.assertFalse(after["reset_bounded_authority"], after)
            self.assertEqual(origin.broker.origins.records, records)


if __name__ == "__main__":
    unittest.main()
