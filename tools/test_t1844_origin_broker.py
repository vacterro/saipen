"""Operator-event kernel with simulated native identity and OS process facts.

This exercises the actual broker, keyed records and consumer. It does not
claim a real Freebuff UI event. The existing broker identity/attack suite
independently tests the native-client authentication boundary.
"""

from __future__ import annotations

import copy
import json
import os
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
from test_hermetic_env import isolate_host_session  # noqa: E402

TEXT = "repair the existing importer without publishing"


def setUpModule():
    isolate_host_session()


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
            + "\nnext_action: PHASE SCOUT " + task
            + "\nblocker: none\ntransition_from: PLAN\nsaipen_version: 8"
            + "\nmode: full\nupdated: 2026-10-21T00:00:00Z"
            + "\ngoal_waves: 0\ngoal_tickets: 0"
            + "\ncontinuation_authority: operator_required\nauthority_until: budget"
            + "\nsafety_valve_mode: hard_wait"
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

    def bind_source(self, proof):
        provenance = {
            "witness": OT.WITNESS_CARRIER,
            "compared_digest": ingress_digest(TEXT),
            "declared_by": OT.DECLARED_HOST_INGRESS,
            "operator_origin": proof,
        }
        result = intake.capture(self.root, TEXT, request_provenance=provenance)
        self.assertTrue(result["ok"], result)
        self.assertTrue(self.verify(proof, receipt=result["receipt"])["ok"])
        return result["receipt"]

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

    def test_native_revocation_allows_the_worker_to_receive_a_new_human_event(self):
        first = self.issue()
        self.register(first)
        second = self.issue(event="event-2")
        self.assertTrue(self.broker.handle(
            {"op": "revoke-origin", "host": "claude", "proof": first}, self.native_peer,
        )["ok"])
        self.register(second)
        self.assertTrue(self.verify(second)["ok"])
        self.assertFalse(self.verify(first)["ok"])

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

    def test_bound_source_cannot_cross_task_or_continue_budget_scope(self):
        proof = self.issue(action="continue")
        self.register(proof)
        receipt = self.bind_source(proof)
        self.state("T-2")
        self.assertFalse(self.verify(proof, receipt=receipt)["ok"])
        self.state("T-1", budget="E-2")
        self.assertFalse(self.verify(proof, receipt=receipt)["ok"])

    def test_expired_bound_source_cannot_mint_privileges(self):
        proof = self.issue()
        self.register(proof)
        receipt = self.bind_source(proof)
        self.now += 61
        self.assertFalse(self.verify(proof, receipt=receipt)["ok"])

    def test_malformed_native_action_is_a_refusal_not_an_exception(self):
        for action in ([], {}, None, True):
            with self.subTest(action=action):
                result = self.broker.handle(
                    {
                        "op": "issue-origin", "project": str(self.root),
                        "host": "claude", "session": "session-A",
                        "event": "UserPromptSubmit", "event_id": "bad-action",
                        "request_text": TEXT, "action": action,
                    },
                    self.native_peer,
                )
                self.assertFalse(result["ok"], result)

    def test_native_host_birth_change_cannot_reissue_an_older_event(self):
        self.issue()
        self.facts[10] = HP.ProcessFact(10, None, "fixture-host.exe", "fixture-host", created=9)
        result = self.broker.handle(
            {
                "op": "issue-origin", "project": str(self.root),
                "host": "claude", "session": "session-A",
                "event": "UserPromptSubmit", "event_id": "event-1",
                "request_text": TEXT, "action": "start",
            },
            self.native_peer,
        )
        self.assertFalse(result["ok"], result)

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

    def test_matching_file_transport_still_requires_and_can_use_the_native_event(self):
        proof = self.issue()
        self.register(proof)
        task_file = self.root / "task.txt"
        task_file.write_text(TEXT, encoding="utf-8")
        env = {OT.ENV_TASK_FILE: str(task_file), OT.ENV_HOST_SESSION: "session-A"}
        self.assertEqual(OT.witness(TEXT, env=env, root=self.root)["witness"], OT.WITNESS_MODEL)
        OT.admit_host_ingress(
            {"request_text": TEXT, "session_id": "session-A", "message_id": "native-file",
             "operator_origin": proof}, self.root,
        )
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            provenance = OT.witness(TEXT, env=env, root=self.root)
            self.assertEqual(provenance["witness"], OT.WITNESS_CARRIER)
            self.assertTrue(OT.authority_for_provenance(
                provenance, root=self.root,
            )["user_explicit"])

    def test_historical_model_supplied_is_not_promoted_by_a_later_valid_proof(self):
        proof = self.issue()
        self.register(proof)
        provenance = {
            "witness": OT.WITNESS_MODEL,
            "compared_digest": ingress_digest(TEXT),
            "declared_by": OT.DECLARED_HOST_INGRESS,
            "operator_origin": proof,
        }
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            authority = OT.authority_for_provenance(provenance, root=self.root)
        self.assertFalse(authority["user_explicit"])
        self.assertEqual(authority["witness"], OT.WITNESS_MODEL)

    def test_response_and_decision_callers_require_the_authenticated_action_and_root(self):
        from saipen_engine import decision_request, response_surface

        proof = self.issue(action="report")
        self.register(proof)
        provenance = {
            "witness": OT.WITNESS_CARRIER,
            "compared_digest": ingress_digest(TEXT),
            "declared_by": OT.DECLARED_HOST_INGRESS,
            "operator_origin": proof,
        }
        reason = "operator directive superseded: cc all"
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            self.assertTrue(response_surface.human_response_authority(
                TEXT, provenance, root=self.root,
            ))
            self.assertFalse(response_surface.human_response_authority(TEXT, provenance))
            self.assertFalse(response_surface.human_response_authority(
                TEXT + " substituted", provenance, root=self.root,
            ))
            allowed, _ = decision_request.validate_authority_escalation(
                reason, "fixture", "operator_carrier", provenance=provenance, root=self.root,
            )
            self.assertFalse(allowed, "a report event cannot supersede an operator pause")
        self.assertFalse(decision_request.validate_authority_escalation(
            reason, "fixture", "operator_carrier",
        )[0])

    def test_start_pipeline_binds_the_real_captured_source_before_privileged_projection(self):
        from saipen_engine import entry
        from saipen_engine.board import parse_board
        from saipen_engine.state import parse_state
        from test_t1363_zero_manual_entry import healthy

        self.root = healthy(self)
        proof = self.issue()
        self.register(proof)
        OT.admit_host_ingress(
            {"request_text": TEXT, "session_id": "session-A", "message_id": "native-start",
             "operator_origin": proof},
            self.root,
        )
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
            HC, "_call", side_effect=self.bridge,
        ):
            result = entry.start_work(self.root, "test-agent", text=TEXT, actor_source="fixture")
        self.assertTrue(result["ok"], result)
        tickets = parse_board((self.root / ".saipen/BOARD.md").read_text())["tickets"]
        work = tickets[result["ticket"]]
        self.assertEqual(work["fields"].get("user_explicit"), "true", result)
        current = parse_state((self.root / ".saipen/STATE.md").read_text())
        self.assertEqual(current["task"], work["id"])
        self.assertIsNotNone(self.broker.origins.records[proof["nonce"]]["receipt"])

    def test_continue_capability_can_be_rechecked_in_its_unchanged_scope(self):
        proof = self.issue(action="continue")
        self.register(proof)
        receipt = self.bind_source(proof)
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            for _ in range(2):
                authority = OT.authority_for_receipt(self.root, receipt)
                self.assertTrue(authority["reset_bounded_authority"])
                self.assertFalse(authority["preempt_active_work"])
                self.assertFalse(authority["goal_pivot"])

    def test_consumed_delivery_retries_only_through_its_exact_live_source(self):
        proof = self.issue()
        self.register(proof)
        OT.admit_host_ingress(
            {"request_text": TEXT, "session_id": "session-A", "message_id": "source-retry",
             "operator_origin": proof}, self.root,
        )
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
            HC, "_call", side_effect=self.bridge,
        ):
            provenance = OT.witness(TEXT, root=self.root)
            captured = intake.capture(self.root, TEXT, request_provenance=provenance)
            self.assertTrue(captured["ok"], captured)
            self.assertTrue(OT.authority_for_receipt(
                self.root, captured["receipt"], existing_only=False,
            )["user_explicit"])
            retried = OT.witness(TEXT, root=self.root)
            self.assertEqual(retried["witness"], OT.WITNESS_CARRIER)
            self.assertEqual(retried.get("source_receipt"), captured["receipt"])
            self.assertTrue(OT.authority_for_provenance(retried, root=self.root)["user_explicit"])
            duplicate = intake.capture(self.root, TEXT, request_provenance=retried)
            self.assertEqual(duplicate["receipt"], captured["receipt"])
            self.state("T-2")
            self.assertFalse(OT.authority_for_provenance(retried, root=self.root)["user_explicit"])

    def test_a_source_hint_cannot_bind_an_event_or_borrow_another_worker(self):
        proof = self.issue()
        self.register(proof)
        provenance = {
            "witness": OT.WITNESS_CARRIER, "declared_by": OT.DECLARED_HOST_INGRESS,
            "compared_digest": ingress_digest(TEXT), "operator_origin": proof,
        }
        captured = intake.capture(self.root, TEXT, request_provenance=provenance)
        self.assertTrue(captured["ok"], captured)
        hint = {**provenance, "source_receipt": captured["receipt"]}
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            self.assertFalse(OT.authority_for_provenance(hint, root=self.root)["user_explicit"])
            self.assertIsNone(self.broker.origins.records[proof["nonce"]]["receipt"])
            self.assertTrue(OT.authority_for_receipt(
                self.root, captured["receipt"], existing_only=False,
            )["user_explicit"])
            self.assertTrue(OT.authority_for_provenance(hint, root=self.root)["user_explicit"])
            self.peer = SimpleNamespace(pid=30)
            self.assertFalse(OT.authority_for_provenance(hint, root=self.root)["user_explicit"])

    def test_transport_retirement_is_write_free_and_cannot_change_its_original_source(self):
        admitted = OT.admit_host_ingress(
            {"request_text": TEXT, "session_id": "session-A", "message_id": "retired-cache"},
            self.root,
        )
        self.assertTrue(admitted["ok"], admitted)
        path = OT.ingress_cache_dir(self.root) / f"{admitted['ingress_id']}.json"
        record = json.loads(path.read_text())
        record.update(consumed=True, consumed_by="SRC-001", consumed_at="2000-01-01T00:00:00Z")
        path.write_text(json.dumps(record), encoding="utf-8")
        before = path.read_bytes()
        self.assertTrue(OT.consume_host_ingress(self.root, admitted["ingress_id"], "SRC-001"))
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(OT.consume_host_ingress(self.root, admitted["ingress_id"], "SRC-002"))
        self.assertEqual(path.read_bytes(), before)

    def test_received_source_evidence_preserves_origin_without_restoring_delivery_privilege(self):
        reader = getattr(HC, "verify_operator_source", None)
        self.assertTrue(callable(reader), "the separated owner must attest accepted Source origin")
        proof = self.issue(action="report")
        self.register(proof)
        receipt = self.bind_source(proof)
        original = copy.deepcopy(self.broker.origins.records[proof["nonce"]])
        self.now += 61
        self.peer = SimpleNamespace(pid=30)
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            self.assertTrue(reader(
                proof, project=self.root, receipt=receipt, request_digest=ingress_digest(TEXT),
            ))
            self.assertFalse(OT.authority_for_receipt(self.root, receipt)["user_explicit"])
            self.assertEqual(self.broker.origins.records[proof["nonce"]], original)
            copied = intake.capture(
                self.root, TEXT, force=True,
                request_provenance=intake._read_meta(self.root, receipt)["request_provenance"],
            )
            self.assertTrue(copied["ok"], copied)
            self.assertFalse(reader(
                proof, project=self.root, receipt=copied["receipt"],
                request_digest=ingress_digest(TEXT),
            ))
        revoked = self.broker.handle(
            {"op": "revoke-origin", "host": "claude", "proof": proof}, self.native_peer,
        )
        self.assertTrue(revoked["ok"], revoked)
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            self.assertFalse(reader(
                proof, project=self.root, receipt=receipt, request_digest=ingress_digest(TEXT),
            ))

    def test_received_source_read_cannot_accept_an_unbound_record(self):
        reader = getattr(HC, "verify_operator_source", None)
        self.assertTrue(callable(reader))
        proof = self.issue(action="report")
        self.register(proof)
        captured = intake.capture(self.root, TEXT, request_provenance={
            "witness": OT.WITNESS_CARRIER, "declared_by": OT.DECLARED_HOST_INGRESS,
            "compared_digest": ingress_digest(TEXT), "operator_origin": proof,
        })
        self.assertTrue(captured["ok"], captured)
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            self.assertFalse(reader(
                proof, project=self.root, receipt=captured["receipt"],
                request_digest=ingress_digest(TEXT),
            ))
        self.assertIsNone(self.broker.origins.records[proof["nonce"]]["receipt"])

    def test_received_origin_verdict_cannot_be_used_as_current_operator_authority(self):
        proof = self.issue(action="report")
        self.register(proof)
        receipt = self.bind_source(proof)
        reply = self.broker.handle(
            {"op": "verify-source-origin", "project": str(self.root), "proof": proof,
             "receipt": receipt, "request_digest": ingress_digest(TEXT)}, self.peer,
        )
        self.assertTrue(reply["ok"], reply)
        with mock.patch.object(HC, "_call", return_value=reply):
            self.assertTrue(HC.verify_operator_source(
                proof, project=self.root, receipt=receipt, request_digest=ingress_digest(TEXT),
            ))
            self.assertFalse(HC.verify_operator_origin(
                proof, project=self.root, receipt=receipt, request_digest=ingress_digest(TEXT),
            ))

    def test_existing_only_source_check_never_creates_a_binding(self):
        proof = self.issue()
        self.register(proof)
        provenance = {
            "witness": OT.WITNESS_CARRIER, "compared_digest": ingress_digest(TEXT),
            "declared_by": OT.DECLARED_HOST_INGRESS, "operator_origin": proof,
        }
        captured = intake.capture(self.root, TEXT, request_provenance=provenance)
        self.assertTrue(captured["ok"], captured)
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            authority = OT.authority_for_receipt(
                self.root, captured["receipt"], existing_only=True,
            )
            self.assertFalse(authority["user_explicit"])
            self.assertIsNone(self.broker.origins.records[proof["nonce"]]["receipt"])
            self.assertFalse(OT.authority_for_receipt(
                self.root, captured["receipt"],
            )["user_explicit"], "ordinary authority queries must never accept a Source")
            self.assertIsNone(self.broker.origins.records[proof["nonce"]]["receipt"])
            self.assertTrue(OT.authority_for_receipt(
                self.root, captured["receipt"], existing_only=False,
            )["user_explicit"])

    def enter_goal(self):
        from saipen_engine.operations import goal_entry
        from saipen_engine.state import parse_state
        from test_t1363_zero_manual_entry import healthy

        self.root = healthy(self)
        proof = self.issue(action="goal")
        self.register(proof)
        OT.admit_host_ingress(
            {"request_text": TEXT, "session_id": "session-A", "message_id": "native-goal",
             "operator_origin": proof},
            self.root,
        )
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
            HC, "_call", side_effect=self.bridge,
        ):
            result = goal_entry(self.root, "test-agent", TEXT)
        self.assertTrue(result.ok, (result.code, result.message, result.data))
        return proof, parse_state((self.root / ".saipen/STATE.md").read_text())

    def test_goal_pipeline_retains_only_its_committed_scoped_continuation(self):
        from saipen_engine import goal_authority

        proof, state = self.enter_goal()
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            self.assertEqual(goal_authority.prove(self.root, state), [])
            self.now += 61
            # Existing scoped authority continues; the expired delivery must
            # remain unavailable for another pivot or a counter reset.
            self.assertEqual(goal_authority.prove(self.root, state), [])
            self.assertFalse(OT.authority_for_provenance(
                {"witness": OT.WITNESS_CARRIER, "declared_by": OT.DECLARED_HOST_INGRESS,
                 "compared_digest": ingress_digest(TEXT), "operator_origin": proof},
                root=self.root,
            )["goal_pivot"])
            changed = dict(state, goal_ingress="goal-" + "f" * 16)
            self.assertTrue(goal_authority.prove(self.root, changed))

    def test_committed_goal_refuses_copied_source_wrong_worker_revocation_and_issuer_loss(self):
        from saipen_engine import goal_authority

        proof, state = self.enter_goal()
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            self.assertEqual(goal_authority.prove(self.root, state), [])
            provenance = {
                "witness": OT.WITNESS_CARRIER, "compared_digest": ingress_digest(TEXT),
                "declared_by": OT.DECLARED_HOST_INGRESS, "operator_origin": proof,
            }
            copied = intake.capture(self.root, TEXT, request_provenance=provenance)
            self.assertTrue(copied["ok"], copied)
            self.assertFalse(OT.authority_for_receipt(self.root, copied["receipt"])["goal_pivot"])
            self.peer = SimpleNamespace(pid=30)
            self.assertTrue(goal_authority.prove(self.root, state))
            self.peer = self.worker_peer
            original = self.broker
            with mock.patch.object(HP, "ancestry", side_effect=self.ancestry):
                self.broker = HB.Broker(runtime=Path(self.tmp.name) / "lost-issuer")
            self.assertTrue(goal_authority.prove(self.root, state))
            self.broker = original
            self.assertEqual(goal_authority.prove(self.root, state), [])
            self.assertTrue(self.broker.handle(
                {"op": "revoke-origin", "host": "claude", "proof": proof}, self.native_peer,
            )["ok"])
            self.assertTrue(goal_authority.prove(self.root, state))

    def test_goal_journal_relabeling_is_detected_and_original_remains_valid(self):
        from saipen_engine import goal_authority
        from saipen_engine.journal import Journal

        proof, state = self.enter_goal()
        journal = Journal(self.root, "goal-entry-" + proof["nonce"])
        original = journal.manifest.read_bytes()
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            self.assertEqual(goal_authority.prove(self.root, state), [])
            record = json.loads(original)
            record["receipt_metadata"]["goal_authority"]["request_provenance"][
                "witness"
            ] = OT.WITNESS_MODEL
            journal.manifest.write_text(json.dumps(record), encoding="utf-8")
            self.assertTrue(goal_authority.prove(self.root, state))
            journal.manifest.write_bytes(original)
            self.assertEqual(goal_authority.prove(self.root, state), [])

    def test_a_goal_reservation_cannot_be_rebound_to_another_operation_or_goal(self):
        proof, _ = self.enter_goal()
        reserved = self.broker.origins.records[proof["nonce"]]["goal_grant"]
        for changes in (
            {"operation": "goal-entry-" + "f" * 32},
            {"grant": {**reserved["grant"], "goal_ingress": "goal-" + "f" * 16}},
        ):
            with self.subTest(changes=changes):
                result = self.broker.handle(
                    {"op": "prepare-origin-goal", "project": str(self.root), "proof": proof,
                     **reserved, **changes}, self.peer,
                )
                self.assertFalse(result["ok"], result)

    def test_native_replacement_worker_can_continue_a_committed_goal_after_delivery_expiry(self):
        from saipen_engine import goal_authority

        proof, state = self.enter_goal()
        self.now += 61
        self.register(proof, worker=40)
        self.peer = SimpleNamespace(pid=40)
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            self.assertEqual(goal_authority.prove(self.root, state), [])
        self.assertFalse(
            self.verify(proof)["ok"], "an expired delivery cannot authorize a new action",
        )

    def test_goal_reservation_survives_a_refused_apply_without_another_effect(self):
        from saipen_engine import operations
        from saipen_engine.result import Result
        from test_t1363_zero_manual_entry import healthy

        self.root = healthy(self)
        proof = self.issue(action="goal")
        self.register(proof)
        OT.admit_host_ingress(
            {"request_text": TEXT, "session_id": "session-A", "message_id": "native-retry",
             "operator_origin": proof}, self.root,
        )
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
            HC, "_call", side_effect=self.bridge,
        ):
            with mock.patch.object(
                operations, "apply_plan", return_value=Result(False, "WRITER_BUSY"),
            ):
                first = operations.goal_entry(self.root, "test-agent", TEXT)
            self.assertFalse(first.ok)
            reserved = copy.deepcopy(self.broker.origins.records[proof["nonce"]]["goal_grant"])
            second = operations.goal_entry(self.root, "test-agent", TEXT)
        self.assertTrue(second.ok, (second.code, second.message, second.data))
        self.assertEqual(second.code, "GOAL_SET")
        self.assertEqual(second.op_id, reserved["operation"])
        self.assertEqual(self.broker.origins.records[proof["nonce"]]["goal_grant"], reserved)

    def existing_goal_event(self):
        from saipen_engine import goal_authority, operations
        from saipen_engine.log import read_history_snapshot
        from saipen_engine.state import parse_state
        from test_t1363_zero_manual_entry import healthy

        self.root = healthy(self)
        bounded = operations.set_goal_intent(self.root, "test-agent", TEXT)
        self.assertTrue(bounded.ok, bounded.to_dict())
        state_path = self.root / ".saipen/STATE.md"
        state = parse_state(state_path.read_text())
        binding = goal_authority.current_binding(
            self.root, state, read_history_snapshot(self.root).events, {},
        )
        body = json.dumps(binding, sort_keys=True)
        proof = self.issue(action="authorize-goal", text=body)
        self.register(proof)
        OT.admit_host_ingress(
            {"request_text": body, "session_id": "session-A", "message_id": "native-upgrade",
             "operator_origin": proof}, self.root,
        )
        return body, proof

    def test_existing_goal_authorization_keeps_its_source_and_valid_scoped_continuation(self):
        from saipen_engine import goal_authority, operations
        from saipen_engine.state import parse_state

        body, _proof = self.existing_goal_event()
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
            HC, "_call", side_effect=self.bridge,
        ):
            result = operations.authorize_goal_continuation(self.root, "test-agent", body)
            self.assertTrue(result.ok, result.to_dict())
            state = parse_state((self.root / ".saipen/STATE.md").read_text())
            self.assertEqual(goal_authority.prove(self.root, state), [])
            self.now += 61
            self.assertEqual(goal_authority.prove(self.root, state), [])

    def test_source_bound_goal_authorization_can_retry_a_refused_apply(self):
        from saipen_engine import operations
        from saipen_engine.result import Result

        body, proof = self.existing_goal_event()
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
            HC, "_call", side_effect=self.bridge,
        ):
            with mock.patch.object(
                operations, "apply_plan", return_value=Result(False, "WRITER_BUSY"),
            ):
                first = operations.authorize_goal_continuation(self.root, "test-agent", body)
            self.assertFalse(first.ok)
            receipt = self.broker.origins.records[proof["nonce"]]["receipt"]
            original = copy.deepcopy(self.broker.origins.records[proof["nonce"]])
            before = {
                str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()
            }
            preview = operations.authorize_goal_continuation(
                self.root, "test-agent", body, dry_run=True,
            )
            self.assertTrue(preview.ok, preview.to_dict())
            self.assertEqual(preview.code, "GOAL_AUTHORITY_PREVIEW")
            self.assertEqual(self.broker.origins.records[proof["nonce"]], original)
            self.assertEqual(before, {
                str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()
            })
            second = operations.authorize_goal_continuation(self.root, "test-agent", body)
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual(second.code, "GOAL_AUTHORIZED")
        self.assertEqual(self.broker.origins.records[proof["nonce"]]["receipt"], receipt)

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
            self.assertTrue(OT.authority_for_receipt(
                self.root, first["receipt"], existing_only=False,
            )["user_explicit"])
            self.assertTrue(OT.authority_for_receipt(self.root, first["receipt"])["user_explicit"])
            second = intake.capture(self.root, TEXT, request_provenance=provenance, force=True)
            self.assertTrue(second["ok"], second)
            self.assertFalse(
                OT.authority_for_receipt(self.root, second["receipt"])["user_explicit"]
            )
        self.assertFalse(self.verify(proof)["ok"], "a consumed event is not fresh approval")


    def scoped_gate(self, action):
        from saipen_engine import journal
        from test_t1729_operator_gate import ScopedOperatorDecision, capsule

        scope = ScopedOperatorDecision()
        self.addCleanup(scope.doCleanups)
        self.root = scope.make()
        body = json.dumps(capsule(self.root, resolve=["blocker", "next_action"]), sort_keys=True)
        proof = self.issue(action=action, text=body)
        self.register(proof)
        provenance = {
            "witness": OT.WITNESS_CARRIER, "declared_by": OT.DECLARED_HOST_INGRESS,
            "compared_digest": ingress_digest(body), "operator_origin": proof,
        }
        captured = intake.capture(
            self.root, body, request_provenance=provenance,
            projection_policy=intake.PROJECTION_AUTHORITY_ONLY,
        )
        self.assertTrue(captured["ok"], captured)
        journal.ensure_project_lineage(self.root)
        self.assertTrue(self.verify(
            proof, receipt=captured["receipt"], request_digest=ingress_digest(body),
        )["ok"])
        return scope, captured["receipt"]

    def test_explicit_native_gate_action_can_resolve_its_exact_gate(self):
        from saipen_engine.reconcile import reconcile_protocol_state

        _scope, receipt = self.scoped_gate("resolve-gate")
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            result = reconcile_protocol_state(self.root, "tester", resolve_blocker=receipt)
        self.assertTrue(result["ok"], result)

    def test_report_action_cannot_be_substituted_for_a_gate_decision(self):
        from saipen_engine.reconcile import reconcile_protocol_state

        scope, receipt = self.scoped_gate("report")
        before = scope.canonical(self.root)
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            result = reconcile_protocol_state(self.root, "tester", resolve_blocker=receipt)
        self.assertFalse(result["ok"], result)
        self.assertEqual(scope.canonical(self.root), before)

    def retirement_source(self, action):
        from test_ticket_retirement import authority_text

        body = authority_text("T-77", "SRC-077")
        proof = self.issue(action=action, text=body)
        self.register(proof)
        captured = intake.capture(
            self.root, body, projection_policy=intake.PROJECTION_AUTHORITY_ONLY,
            request_provenance={
                "witness": OT.WITNESS_CARRIER, "declared_by": OT.DECLARED_HOST_INGRESS,
                "compared_digest": ingress_digest(body), "operator_origin": proof,
            },
        )
        self.assertTrue(captured["ok"], captured)
        self.assertTrue(self.verify(
            proof, receipt=captured["receipt"], request_digest=ingress_digest(body),
        )["ok"])
        return captured["receipt"]

    def test_native_retirement_action_can_authorize_its_exact_capsule(self):
        from saipen_engine import retirement

        receipt = self.retirement_source("retire")
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            problem, binding = retirement.authority_error(
                self.root, receipt, ticket_id="T-77", receipts=["SRC-077"],
            )
        self.assertIsNone(problem, problem)
        self.assertIsNotNone(binding)

    def test_report_event_cannot_be_substituted_for_retirement_authority(self):
        from saipen_engine import retirement

        receipt = self.retirement_source("report")
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            problem, binding = retirement.authority_error(
                self.root, receipt, ticket_id="T-77", receipts=["SRC-077"],
            )
        self.assertIsNotNone(problem)
        self.assertIsNone(binding)

    def test_bound_retirement_continues_only_within_its_original_goal_and_budget(self):
        from saipen_engine import retirement

        receipt = self.retirement_source("retire")
        with mock.patch.object(HC, "_call", side_effect=self.bridge):
            def allowed():
                return retirement.authority_error(
                    self.root, receipt, ticket_id="T-77", receipts=["SRC-077"],
                )[0] is None

            self.assertTrue(allowed())
            self.state("T-2")
            self.assertTrue(allowed(), "the accepted capsule still names exactly T-77/SRC-077")
            self.state("T-2", budget="E-2")
            self.assertFalse(allowed(), "a bound Source must not cross its accepted budget epoch")

    def test_claim_handoff_requires_its_native_action(self):
        from saipen_engine import handoff

        body = f"{handoff.GRANT_HEADER}\nT-77 -> next-agent\n{handoff.GRANT_TERMINATOR}\n"
        for action, expected in (("report", False), ("handoff", True)):
            proof = self.issue(action=action, text=body, event="handoff-" + action)
            self.register(proof, worker=20 if action == "report" else 40)
            self.peer = SimpleNamespace(pid=21 if action == "report" else 40)
            captured = intake.capture(
                self.root, body, projection_policy=intake.PROJECTION_AUTHORITY_ONLY,
                request_provenance={
                    "witness": OT.WITNESS_CARRIER, "declared_by": OT.DECLARED_HOST_INGRESS,
                    "compared_digest": ingress_digest(body), "operator_origin": proof,
                },
            )
            self.assertTrue(captured["ok"], captured)
            self.assertTrue(self.verify(
                proof, receipt=captured["receipt"], request_digest=ingress_digest(body),
            )["ok"])
            with mock.patch.object(HC, "_call", side_effect=self.bridge):
                problem = handoff.authority_error(
                    self.root, captured["receipt"], ticket="T-77", agent="next-agent",
                )
            self.assertEqual(problem is None, expected, (action, problem))

    def test_work_supersession_requires_a_native_supersession_event(self):
        from saipen_engine import supersession

        body = f"{supersession.GRANT_HEADER}\nT-77 - T-78\n{supersession.GRANT_TERMINATOR}\n"
        for action, expected in ((None, False), ("report", False), ("supersede", True)):
            provenance = None
            if action:
                proof = self.issue(action=action, text=body, event="supersede-" + action)
                worker = 20 if action == "report" else 40
                self.register(proof, worker=worker)
                self.peer = SimpleNamespace(pid=worker)
                provenance = {
                    "witness": OT.WITNESS_CARRIER, "declared_by": OT.DECLARED_HOST_INGRESS,
                    "compared_digest": ingress_digest(body), "operator_origin": proof,
                }
            captured = intake.capture(self.root, body, request_provenance=provenance)
            self.assertTrue(captured["ok"], captured)
            if action:
                self.assertTrue(self.verify(
                    proof, receipt=captured["receipt"], request_digest=ingress_digest(body),
                )["ok"])
            with mock.patch.object(HC, "_call", side_effect=self.bridge):
                problem, _binding = supersession.authority_error(
                    self.root, captured["receipt"], old_ticket="T-77", successor_ticket="T-78",
                )
            self.assertEqual(problem is None, expected, (action, problem))

    def test_revoked_origin_refusal_remains_a_registered_native_code(self):
        from saipen_engine import operations
        from test_t1363_zero_manual_entry import healthy
        from test_ticket_retirement import authority_text

        self.root = healthy(self)
        body = authority_text("T-77", "SRC-077")
        proof = self.issue(action="retire", text=body)
        self.register(proof)
        OT.admit_host_ingress(
            {"request_text": body, "session_id": "session-A", "message_id": "revoked-source",
             "operator_origin": proof}, self.root,
        )
        revoked = self.broker.handle(
            {"op": "revoke-origin", "host": "claude", "proof": proof}, self.native_peer,
        )
        self.assertTrue(revoked["ok"], revoked)
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
            HC, "_call", side_effect=self.bridge,
        ):
            result = operations.authority_capture(self.root, "test-agent", body)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, OT.CODE_HOST_PROVENANCE_UNAVAILABLE)
        self.assertFalse((result.data or {}).get("unregistered_code"), result.to_dict())


if __name__ == "__main__":
    unittest.main()
