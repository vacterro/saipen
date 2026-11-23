"""Operator-event kernel with simulated native identity and OS process facts.

This exercises the actual broker, keyed records and consumer. It does not
claim a real Freebuff UI event. The existing broker identity/attack suite
independently tests the native-client authentication boundary.
"""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_authority_broker as HB  # noqa: E402
from saipen_engine import host_authority_client as HC  # noqa: E402
from saipen_engine import host_authority_process as HP  # noqa: E402
from saipen_engine import intake, operator_task as OT  # noqa: E402
from saipen_engine.pending_ingress import ingress_digest  # noqa: E402

TEXT = "repair the existing importer without publishing"


class OriginKernelWithSimulatedNativeIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="t1844-origin-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        (self.root / ".saipen").mkdir(parents=True)
        self.state("T-1")
        (self.root / ".saipen/IDENTITY.md").write_text(
            "---\nproject_lineage: lineage-0123456789abcdef0123456789abcdef\n---\n",
            encoding="utf-8",
        )
        self.now = 100.0
        self.facts = {
            10: HP.ProcessFact(10, None, "fixture-host.exe", "fixture-host", created=1),
            20: HP.ProcessFact(20, 10, "worker.exe", "worker", created=2),
            21: HP.ProcessFact(21, 20, "engine.exe", "engine", created=3),
            30: HP.ProcessFact(30, 10, "unregistered.exe", "unregistered", created=4),
            40: HP.ProcessFact(40, 10, "other-worker.exe", "other-worker", created=5),
        }
        with mock.patch.object(HP, "ancestry", side_effect=self.ancestry):
            self.broker = HB.Broker(
                runtime=Path(self.tmp.name) / "isolated-broker",
                clock=lambda: self.now,
                config={"capability_ttl_seconds": 60},
                authenticator=self.native,
            )
        self.native_peer = SimpleNamespace(pid=100, kind="simulated-native")
        self.worker_peer = SimpleNamespace(pid=21, kind="simulated-worker")
        self.peer = self.worker_peer

    def state(self, task, budget="E-1"):
        (self.root / ".saipen/STATE.md").write_text(
            "---\nphase: SCOUT\nagent: fixture\ntask: "
            + task
            + "\nexecution_intent: goal\ngoal_ingress: goal-1\nauthority_source: "
            + budget
            + "\n---\n",
            encoding="utf-8",
        )

    def ancestry(self, pid, limit=32):
        result = []
        while pid in self.facts and len(result) < limit:
            fact = self.facts[pid]
            result.append(fact)
            pid = fact.ppid
        return result

    @staticmethod
    def native(peer, host, home):
        if getattr(peer, "pid", None) == 100:
            return True, None, {"host_pid": 10, "hook_pid": 100, "detail": "simulated"}
        return False, HB.CODE_NOT_AUTHENTICATED, {"detail": "not the native callback"}

    def issue(self, *, action="start", event="event-1", session="session-A", text=TEXT):
        result = self.broker.handle(
            {
                "op": "issue-origin",
                "project": str(self.root),
                "session": session,
                "host": "claude",
                "event": "UserPromptSubmit",
                "request_text": text,
                "event_id": event,
                "action": action,
            },
            self.native_peer,
        )
        self.assertTrue(result.get("ok"), result)
        return result["proof"]

    def register(self, proof, worker=20):
        result = self.broker.handle(
            {
                "op": "register-origin-worker",
                "host": "claude",
                "proof": proof,
                "worker": worker,
            },
            self.native_peer,
        )
        self.assertTrue(result.get("ok"), result)

    def verify(self, proof, **changes):
        payload = {
            "op": "verify-origin",
            "proof": proof,
            "project": str(self.root),
            "request_digest": ingress_digest(TEXT),
            **changes,
        }
        return self.broker.handle(payload, self.peer)

    def bridge(self, payload, *, runtime, timeout):
        self.assertIsNone(runtime, "consumer must not choose a diagnostic authority")
        return self.broker.handle(payload, self.peer)

    def test_actual_broker_refuses_model_issuer_even_with_claimed_flags(self):
        result = self.broker.handle(
            {
                "op": "issue-origin",
                "project": str(self.root),
                "host": "claude",
                "session": "session-A",
                "event": "UserPromptSubmit",
                "event_id": "fake",
                "request_text": TEXT,
                "action": "goal",
                "authenticated": True,
                "host_pid": 10,
            },
            self.worker_peer,
        )
        self.assertFalse(result["ok"], result)
        self.assertEqual(len(self.broker.origins.records), 0)

    def test_native_issue_then_registered_nested_worker_can_verify(self):
        proof = self.issue()
        self.assertFalse(self.verify(proof)["ok"])
        self.register(proof)
        result = self.verify(proof)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["action"], "start")

    def test_matching_session_env_cannot_replace_registered_os_worker(self):
        proof = self.issue()
        self.register(proof)
        self.peer = SimpleNamespace(pid=30)
        self.assertFalse(self.verify(proof, session="session-A")["ok"])

    def test_another_registered_session_cannot_borrow_the_proof(self):
        first = self.issue()
        second = self.issue(event="event-2", session="session-B")
        self.register(first)
        self.register(second, 40)
        self.peer = SimpleNamespace(pid=40)
        self.assertFalse(self.verify(first, session="session-A")["ok"])

    def test_native_host_process_is_never_a_shared_model_worker(self):
        proof = self.issue()
        result = self.broker.handle(
            {"op": "register-origin-worker", "host": "claude", "proof": proof, "worker": 10},
            self.native_peer,
        )
        self.assertFalse(result["ok"], result)

    def test_worker_registration_itself_requires_native_identity(self):
        proof = self.issue()
        result = self.broker.handle(
            {"op": "register-origin-worker", "host": "claude", "proof": proof, "worker": 20},
            self.worker_peer,
        )
        self.assertFalse(result["ok"], result)

    def test_a_live_worker_cannot_be_transplanted_between_events(self):
        first = self.issue()
        second = self.issue(event="event-2", session="session-B")
        self.register(first)
        result = self.broker.handle(
            {"op": "register-origin-worker", "host": "claude", "proof": second, "worker": 20},
            self.native_peer,
        )
        self.assertFalse(result["ok"], result)

    def test_pid_reuse_and_broken_ancestry_refuse(self):
        proof = self.issue()
        self.register(proof)
        self.facts[20] = HP.ProcessFact(20, 10, "other.exe", "other", created=8)
        self.assertFalse(self.verify(proof)["ok"])

    def test_native_event_redelivery_is_idempotent_but_changed_text_refuses(self):
        proof = self.issue()
        self.assertEqual(self.issue(), proof)
        result = self.broker.handle(
            {
                "op": "issue-origin",
                "project": str(self.root),
                "session": "session-A",
                "host": "claude",
                "event": "UserPromptSubmit",
                "request_text": TEXT + " broadened",
                "event_id": "event-1",
                "action": "start",
            },
            self.native_peer,
        )
        self.assertFalse(result["ok"], result)
        self.assertEqual(len(self.broker.origins.records), 1)

    def test_tampering_different_content_and_other_project_refuse(self):
        proof = self.issue()
        self.register(proof)
        altered = copy.deepcopy(proof)
        altered["action"] = "goal"
        self.assertFalse(self.verify(altered)["ok"])
        self.assertFalse(self.verify(proof, request_digest="0" * 64)["ok"])
        self.assertFalse(self.verify(proof, project=str(self.root.parent))["ok"])

    def test_expiry_revocation_and_issuer_loss_refuse(self):
        proof = self.issue()
        self.register(proof)
        self.now += 61
        self.assertFalse(self.verify(proof)["ok"])
        self.now -= 61
        result = self.broker.handle(
            {"op": "revoke-origin", "host": "claude", "proof": proof}, self.native_peer
        )
        self.assertTrue(result["ok"], result)
        self.assertFalse(self.verify(proof)["ok"])
        with mock.patch.object(HP, "ancestry", side_effect=self.ancestry):
            other = HB.Broker(runtime=Path(self.tmp.name) / "other", clock=lambda: self.now)
        self.assertFalse(
            other.handle(
                {"op": "verify-origin", "proof": proof, "project": str(self.root)}, self.peer
            )["ok"]
        )

    def test_task_and_continue_budget_epoch_cannot_be_replayed(self):
        proof = self.issue(action="continue")
        self.register(proof)
        self.state("T-1", budget="E-2")
        self.assertFalse(self.verify(proof)["ok"])
        self.state("T-2")
        self.assertFalse(self.verify(proof)["ok"])

    def test_malformed_proof_is_a_refusal_not_a_service_exception(self):
        for value in (
            None,
            [],
            {"kind": "operator-origin", "nonce": {}},
            {"kind": "operator-origin", "nonce": "0" * 32},
        ):
            with self.subTest(value=value):
                self.assertFalse(self.verify(value)["ok"])

    def test_actual_consumer_authenticates_only_its_permitted_action(self):
        proof = self.issue()
        self.register(proof)
        OT.admit_host_ingress(
            {
                "request_text": TEXT,
                "session_id": "session-A",
                "message_id": "native-message",
                "operator_origin": proof,
            },
            self.root,
        )
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            provenance = OT.witness(TEXT, env={OT.ENV_HOST_SESSION: "session-A"}, root=self.root)
            authority = OT.authority_for_provenance(provenance, root=self.root)
        self.assertTrue(authority["user_explicit"], (provenance, authority))
        self.assertTrue(authority["preempt_active_work"])
        self.assertFalse(authority["goal_pivot"], "a start event is not a new-goal approval")
        self.assertFalse(authority["reset_bounded_authority"])

    def test_source_binding_preserves_the_accepted_origin_and_refuses_a_second_source(self):
        proof = self.issue()
        self.register(proof)
        provenance = {
            "witness": OT.WITNESS_CARRIER,
            "compared_digest": ingress_digest(TEXT),
            "declared_by": OT.DECLARED_HOST_INGRESS,
            "operator_origin": proof,
        }
        first = intake.capture(self.root, TEXT, request_provenance=provenance)
        self.assertTrue(first["ok"], first)
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            self.assertTrue(OT.authority_for_receipt(self.root, first["receipt"])["user_explicit"])
            self.assertTrue(OT.authority_for_receipt(self.root, first["receipt"])["user_explicit"])
            second = intake.capture(self.root, TEXT, request_provenance=provenance, force=True)
            self.assertTrue(second["ok"], second)
            self.assertFalse(
                OT.authority_for_receipt(self.root, second["receipt"])["user_explicit"]
            )
        self.assertFalse(self.verify(proof)["ok"], "a consumed event is not fresh approval")


if __name__ == "__main__":
    unittest.main()
