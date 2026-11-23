"""Campaign grants through the actual broker kernel with simulated OS/native peers.

Keyed origin issuance and grant verification are real. Native identity/process
facts are simulated; this suite does not claim genuine host/operator acceptance.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from saipen_engine import campaign, host_authority_broker as HB, host_authority_client as HC
from saipen_engine import host_authority_process as HP, intake, operator_task
from saipen_engine import continuation_assessment as ca
from saipen_engine import entry, guard_events
from saipen_engine.pending_ingress import ingress_digest


class CampaignAuthorityKernelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-campaign-authority-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        (self.root / ".saipen").mkdir(parents=True)
        (self.root / ".saipen/STATE.md").write_text(
            "---\nphase: BUILD\ntask: T-1\nagent: fixture\nlast_event: 1\n"
            "next_action: PHASE BUILD T-1\nblocker: none\ntransition_from: SCOUT\n"
            "saipen_version: 8\nmode: full\nupdated: 2026-10-21T00:00:00Z\n"
            "goal_ingress: goal-1\nauthority_source: E-1\nexecution_intent: goal\n"
            "goal_waves: 0\ngoal_tickets: 0\ncontinuation_authority: operator_required\n"
            "authority_until: budget\nsafety_valve_mode: hard_wait\n---\n",
            encoding="utf-8",
        )
        self.lineage = "lineage-0123456789abcdef0123456789abcdef"
        (self.root / ".saipen/IDENTITY.md").write_text(
            f"---\nproject_lineage: {self.lineage}\n---\n",
            encoding="utf-8",
        )
        (self.root / ".saipen/BOARD.md").write_text(
            "## DOING\n- [/] T-1 [P2] Task\n", encoding="utf-8"
        )
        (self.root / ".saipen/LOG.md").write_text("# LOG\n", encoding="utf-8")
        self.now = 100.0
        self.facts = {
            10: HP.ProcessFact(10, None, "fixture-host.exe", "fixture-host", created=1),
            20: HP.ProcessFact(20, 10, "worker.exe", "worker", created=2),
            21: HP.ProcessFact(21, 20, "engine.exe", "engine", created=3),
            30: HP.ProcessFact(30, 10, "unregistered.exe", "unregistered", created=4),
        }
        with mock.patch.object(HP, "ancestry", side_effect=self.ancestry):
            self.broker = HB.Broker(
                runtime=Path(self.tmp.name) / "broker",
                clock=lambda: self.now,
                config={"capability_ttl_seconds": 60},
                authenticator=self.native,
            )
        self.native_peer = SimpleNamespace(pid=100, kind="simulated-native")
        self.peer = SimpleNamespace(pid=21, kind="simulated-worker")
        self.enterContext(mock.patch.object(HC, "_call", side_effect=self.bridge))
        self.authorization = {
            "schema_version": 1,
            "kind": "saipen-campaign-authorization",
            "campaign_limit": 1,
            "project_lineage": self.lineage,
            "target_project": str(self.root),
            "host": "claude",
            "session": "session-A",
            "goal_binding": {"goal_ingress": "goal-1", "authority_source": "E-1"},
            "authorized_scopes": [campaign.CAMPAIGN_EXECUTION, campaign.AUDIT_STAGING],
            "resource_budget": {"max_generations": 5, "max_cycles": 10, "max_wall_seconds": 300},
            "expires_at": 1000.0,
        }
        self.admission = {
            "campaign_id": "CAMP-1",
            "goal_binding": self.authorization["goal_binding"],
            "resource_budget": dict(self.authorization["resource_budget"]),
        }

    def ancestry(self, pid, limit=32):
        chain = []
        while pid in self.facts and len(chain) < limit:
            chain.append(self.facts[pid])
            pid = self.facts[pid].ppid
        return chain

    @staticmethod
    def native(peer, host, home):
        return (
            (True, None, {"host_pid": 10, "hook_pid": 100, "detail": "simulated"})
            if peer.pid == 100
            else (False, HB.CODE_NOT_AUTHENTICATED, {})
        )

    def bridge(self, payload, *, runtime, timeout):
        self.assertIsNone(runtime, "a model must not choose a diagnostic authority endpoint")
        return self.broker.handle(payload, self.peer)

    def issue(self, text, *, action="start", event="event-1", register=True):
        result = self.broker.handle(
            {
                "op": "issue-origin",
                "project": str(self.root),
                "session": "session-A",
                "host": "claude",
                "event": "UserPromptSubmit",
                "event_id": event,
                "request_text": text,
                "action": action,
            },
            self.native_peer,
        )
        self.assertTrue(result["ok"], result)
        proof = result["proof"]
        if register:
            result = self.broker.handle(
                {"op": "register-origin-worker", "host": "claude", "proof": proof, "worker": 20},
                self.native_peer,
            )
            self.assertTrue(result["ok"], result)
        return proof

    def carrier(self, *, authorization=None, event="event-1"):
        authorization = self.authorization if authorization is None else authorization
        text = json.dumps(authorization)
        self.proof = self.issue(text, event=event)
        body = {
            "kind": "saipen-campaign-grant",
            "schema_version": 1,
            "request_text": text,
            "operator_origin": self.proof,
        }
        path = self.root / "grant.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        return path

    def verify(self, path, scope=None, *, admission=None, consume=False):
        return campaign.verify_operator_grant(
            self.root, str(path), scope, admission=admission, consume=consume
        )

    def test_real_origin_for_innocent_text_cannot_sign_caller_selected_scopes(self):
        text = "repair an importer without publishing"
        proof = self.issue(text)
        carrier = {
            "issuer": "operator_broker",
            "project_lineage": self.lineage,
            "operator_origin": proof,
            "request_digest": ingress_digest(text),
            "authorized_scopes": list(campaign.ALL_SCOPES),
        }
        path = self.root / "old-grant.json"
        path.write_text(json.dumps(carrier), encoding="utf-8")
        with mock.patch("time.time", return_value=self.now):
            result = campaign.verify_operator_grant(
                self.root, str(path), campaign.EXTERNAL_AUDIT_PUBLICATION
            )
        self.assertFalse(result["valid"], result)

    def test_real_goal_source_does_not_implicitly_authorize_publication(self):
        text = "repair an importer without publishing"
        proof = self.issue(text, action="goal")
        provenance = {
            "witness": "operator_carrier",
            "compared_digest": ingress_digest(text),
            "declared_by": operator_task.DECLARED_HOST_INGRESS,
            "operator_origin": proof,
        }
        result = intake.capture(self.root, text, request_provenance=provenance)
        self.assertTrue(result["ok"], result)
        binding = self.broker.handle(
            {
                "op": "verify-origin",
                "project": str(self.root),
                "proof": proof,
                "request_digest": ingress_digest(text),
                "receipt": result["receipt"],
            },
            self.peer,
        )
        self.assertTrue(binding["ok"], binding)
        self.assertFalse(
            campaign.verify_operator_grant(
                self.root, result["receipt"], campaign.EXTERNAL_AUDIT_PUBLICATION
            )["valid"]
        )

    def test_exact_native_capsule_grants_only_declared_scopes(self):
        path = self.carrier()
        result = self.verify(
            path, campaign.CAMPAIGN_EXECUTION, admission=self.admission, consume=True
        )
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["authorized_scopes"], set(self.authorization["authorized_scopes"]))
        self.assertFalse(
            self.verify(path, campaign.EXTERNAL_AUDIT_PUBLICATION, admission=self.admission)[
                "valid"
            ]
        )

    def test_native_capsule_source_can_use_the_same_canonical_verifier(self):
        text = json.dumps(self.authorization)
        proof = self.issue(text)
        provenance = {
            "witness": "operator_carrier",
            "compared_digest": ingress_digest(text),
            "declared_by": operator_task.DECLARED_HOST_INGRESS,
            "operator_origin": proof,
        }
        source = intake.capture(self.root, text, request_provenance=provenance)
        self.assertTrue(source["ok"], source)
        result = self.verify(
            source["receipt"], campaign.CAMPAIGN_EXECUTION, admission=self.admission, consume=True
        )
        self.assertTrue(result["valid"], result)

    def test_standard_request_wrapper_preserves_the_exact_original_permission(self):
        from saipen_engine.operations import _user_request_body

        text = json.dumps(self.authorization)
        proof = self.issue(text)
        body = _user_request_body(text, "P1", "original request", [], None)
        provenance = {
            "witness": "operator_carrier",
            "compared_digest": ingress_digest(text),
            "declared_by": operator_task.DECLARED_HOST_INGRESS,
            "operator_origin": proof,
        }
        source = intake.capture(self.root, body, request_provenance=provenance)
        self.assertTrue(source["ok"], source)
        self.assertTrue(
            self.verify(source["receipt"], admission=self.admission, consume=True)["valid"]
        )

    def test_start_captures_native_authority_without_preempting_work_or_goal(self):
        text = json.dumps(self.authorization)
        proof = self.issue(text)
        provenance = {
            "witness": "operator_carrier",
            "compared_digest": ingress_digest(text),
            "declared_by": operator_task.DECLARED_HOST_INGRESS,
            "operator_origin": proof,
            "session_id": "session-A",
        }
        before = {
            name: (self.root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        with mock.patch.object(operator_task, "witness", return_value=provenance), mock.patch(
            "saipen_engine.watchdog.carrier_present",
            return_value=False,
        ):
            result = entry.start_work(
                self.root, "fixture", actor_source="simulated-native", text=text
            )
            retry = entry.start_work(
                self.root, "fixture", actor_source="simulated-native", text=text
            )
        self.assertTrue(result["ok"], result)
        self.assertEqual(retry.get("receipt"), result["receipt"], retry)
        self.assertEqual(result["code"], "CAMPAIGN_AUTHORITY_RECEIVED")
        self.assertEqual(guard_events._saipen_cli_verb(result["action"]), "campaign")
        for name, body in before.items():
            self.assertEqual((self.root / ".saipen" / name).read_bytes(), body)
        admitted = campaign.CampaignController(self.root).admit_campaign(
            campaign_id="CAMP-1",
            authority_proof_reference=result["receipt"],
        )
        self.assertTrue(admitted["admitted"], admitted)

    def test_start_authority_preview_does_not_capture_or_reserve(self):
        text = json.dumps(self.authorization)
        proof = self.issue(text)
        provenance = {
            "witness": "operator_carrier",
            "compared_digest": ingress_digest(text),
            "declared_by": operator_task.DECLARED_HOST_INGRESS,
            "operator_origin": proof,
            "session_id": "session-A",
        }
        with mock.patch.object(operator_task, "witness", return_value=provenance), mock.patch(
            "saipen_engine.watchdog.carrier_present",
            return_value=False,
        ):
            result = entry.start_work(
                self.root, "fixture", actor_source="simulated-native", text=text, dry_run=True
            )
        self.assertEqual(result["code"], "PLAN")
        self.assertFalse((self.root / ".saipen/intake").exists())
        self.assertNotIn("campaign_grant", self.broker.origins.records[proof["nonce"]])

    def test_authority_capture_respects_conflicting_intake_recovery(self):
        text = json.dumps(self.authorization)
        proof = self.issue(text)
        provenance = {
            "witness": "operator_carrier",
            "compared_digest": ingress_digest(text),
            "declared_by": operator_task.DECLARED_HOST_INGRESS,
            "operator_origin": proof,
            "session_id": "session-A",
        }
        with mock.patch.object(operator_task, "witness", return_value=provenance), mock.patch(
            "saipen_engine.watchdog.carrier_present",
            return_value=False,
        ), mock.patch.object(
            entry, "_pending_touches_intake", return_value=True
        ), mock.patch.object(
            entry,
            "recovery_preflight",
            return_value={"ok": False, "code": "RECOVERY_CONFLICT"},
        ):
            result = entry.start_work(
                self.root, "fixture", actor_source="simulated-native", text=text
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "RECOVERY_CONFLICT")
        self.assertFalse((self.root / ".saipen/intake").exists())

    def test_capsule_edit_cannot_borrow_an_unchanged_origin_proof(self):
        path = self.carrier()
        data = json.loads(path.read_text(encoding="utf-8"))
        auth = json.loads(data["request_text"])
        auth["authorized_scopes"].append(campaign.EXTERNAL_AUDIT_PUBLICATION)
        data["request_text"] = json.dumps(auth)
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertFalse(
            self.verify(
                path, campaign.EXTERNAL_AUDIT_PUBLICATION, admission=self.admission, consume=True
            )["valid"]
        )

    def test_original_carrier_bytes_are_pinned_after_admission(self):
        path = self.carrier()
        self.assertTrue(self.verify(path, admission=self.admission, consume=True)["valid"])
        path.write_bytes(path.read_bytes() + b" ")
        self.assertFalse(self.verify(path, admission=self.admission)["valid"])

    def test_consumption_is_one_campaign_and_exact_retry_is_idempotent(self):
        path = self.carrier()
        for _ in range(2):
            self.assertTrue(self.verify(path, admission=self.admission, consume=True)["valid"])
        foreign = {**self.admission, "campaign_id": "OTHER"}
        self.assertFalse(self.verify(path, admission=foreign, consume=True)["valid"])

    def test_resource_limits_and_goal_binding_are_independently_bound(self):
        path = self.carrier()
        for changes in (
            {"resource_budget": {**self.admission["resource_budget"], "max_cycles": 999}},
            {"goal_binding": {"goal_ingress": "other", "authority_source": "E-1"}},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(
                    self.verify(path, admission={**self.admission, **changes}, consume=True)[
                        "valid"
                    ]
                )

    def test_revocation_expiry_foreign_lineage_and_unregistered_worker_refuse(self):
        path = self.carrier()
        self.peer = SimpleNamespace(pid=30)
        self.assertFalse(self.verify(path, admission=self.admission, consume=True)["valid"])
        self.peer = SimpleNamespace(pid=21)
        self.assertTrue(self.verify(path, admission=self.admission, consume=True)["valid"])
        self.now = 1001
        self.assertFalse(self.verify(path, admission=self.admission)["valid"])
        self.now = 101
        revoked = self.broker.origins.revoke(self.proof, {"host_pid": 10})
        self.assertTrue(revoked["ok"])
        self.assertFalse(self.verify(path, admission=self.admission)["valid"])

    def test_foreign_goal_epoch_and_capsule_target_refuse(self):
        path = self.carrier()
        self.assertTrue(self.verify(path, admission=self.admission, consume=True)["valid"])
        state = self.root / ".saipen/STATE.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace("goal-1", "goal-2"), encoding="utf-8"
        )
        self.assertFalse(self.verify(path, admission=self.admission)["valid"])

    def test_declared_foreign_lineage_host_session_and_target_are_refused(self):
        for number, changed in enumerate(
            (
                {"project_lineage": "lineage-ffffffffffffffffffffffffffffffff"},
                {"host": "other-host"},
                {"session": "other-session"},
                {"target_project": str(self.root.parent / "foreign")},
            )
        ):
            with self.subTest(changed=changed):
                path = self.carrier(
                    authorization={**self.authorization, **changed}, event=f"foreign-{number}"
                )
                self.assertFalse(self.verify(path, admission=self.admission, consume=True)["valid"])
                self.broker.origins.revoke(self.proof, {"host_pid": 10})

    def test_read_only_validation_does_not_admit_an_unconsumed_campaign(self):
        path = self.carrier()
        self.assertFalse(self.verify(path, admission=self.admission)["valid"])
        self.assertNotIn("campaign_grant", self.broker.origins.records[self.proof["nonce"]])

    def test_malformed_issuer_reply_fails_closed_without_traceback(self):
        path = self.carrier()
        for reply in (None, [], ["unrelated"], "unrelated", True, 7, {"ok": True}):
            with self.subTest(reply=reply), mock.patch.object(
                HC, "inspect_operator_campaign", return_value=reply
            ):
                self.assertFalse(self.verify(path, admission=self.admission, consume=True)["valid"])

    def test_structurally_invalid_resource_or_expiry_does_not_mint_authority(self):
        for number, changes in enumerate(
            (
                {"expires_at": 10**500},
                {"expires_at": True},
                {"expires_at": float("nan")},
                {
                    "resource_budget": {
                        "max_generations": True,
                        "max_cycles": 10,
                        "max_wall_seconds": 300,
                    }
                },
                {"authorized_scopes": [campaign.CAMPAIGN_EXECUTION, campaign.CAMPAIGN_EXECUTION]},
            )
        ):
            with self.subTest(changes=changes):
                path = self.carrier(
                    authorization={**self.authorization, **changes}, event=f"invalid-{number}"
                )
                try:
                    self.assertFalse(
                        self.verify(path, admission=self.admission, consume=True)["valid"]
                    )
                finally:
                    self.broker.origins.revoke(self.proof, {"host_pid": 10})

    def test_cancelled_campaign_cannot_spend_its_old_permission(self):
        path = self.carrier()
        ctrl = campaign.CampaignController(self.root)
        self.assertTrue(
            ctrl.admit_campaign(campaign_id="CAMP-1", authority_proof_reference=str(path))[
                "admitted"
            ]
        )
        ctrl.cancel()
        self.assertFalse(self.verify(path, admission=self.admission)["valid"])

    def test_controller_admission_and_revalidation_use_the_bound_budget(self):
        path = self.carrier()
        ctrl = campaign.CampaignController(self.root)
        result = ctrl.admit_campaign(campaign_id="CAMP-1", authority_proof_reference=str(path))
        self.assertTrue(result["admitted"], result)
        path.write_bytes(path.read_bytes() + b" ")
        worker = mock.Mock(return_value={"ok": True})
        result = ctrl.step(worker_func=worker)
        self.assertEqual(result["event"], "AUTHORITY_BLOCKED")
        worker.assert_not_called()

    def test_admitted_original_permission_remains_valid_for_a_real_worker_invocation(self):
        path = self.carrier()
        ctrl = campaign.CampaignController(self.root)
        admitted = ctrl.admit_campaign(campaign_id="CAMP-1", authority_proof_reference=str(path))
        self.assertTrue(admitted["admitted"], admitted)
        worker = mock.Mock(return_value={"ok": True})
        with mock.patch.object(
            ca, "assess_continuation", return_value={"classification": ca.ACTIVE_WORK}
        ):
            result = ctrl.step(worker_func=worker)
        self.assertTrue(result["ok"], result)
        worker.assert_called_once()
        self.assertEqual(result["state"]["worker_generation"], 1)

    def test_revocation_during_assessment_prevents_the_protected_worker_start(self):
        path = self.carrier()
        ctrl = campaign.CampaignController(self.root)
        self.assertTrue(
            ctrl.admit_campaign(campaign_id="CAMP-1", authority_proof_reference=str(path))[
                "admitted"
            ]
        )

        def assess(root):
            self.broker.origins.revoke(self.proof, {"host_pid": 10})
            return {"classification": ca.ACTIVE_WORK}

        worker = mock.Mock(return_value={"ok": True})
        with mock.patch.object(ca, "assess_continuation", side_effect=assess):
            result = ctrl.step(worker_func=worker)
        worker.assert_not_called()
        self.assertEqual(result["event"], "AUTHORITY_BLOCKED")

    def test_delivery_expiry_does_not_shrink_the_explicit_accepted_campaign_lifetime(self):
        path = self.carrier()
        ctrl = campaign.CampaignController(self.root)
        self.assertTrue(
            ctrl.admit_campaign(campaign_id="CAMP-1", authority_proof_reference=str(path))[
                "admitted"
            ]
        )
        self.now = 161
        self.assertTrue(self.verify(path, admission=self.admission)["valid"])
        self.now = 401
        self.assertFalse(self.verify(path, admission=self.admission)["valid"])


if __name__ == "__main__":
    unittest.main()
