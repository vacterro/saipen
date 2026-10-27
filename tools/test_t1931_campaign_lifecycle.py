"""SRC-337 lifecycle controls; local contracts, not installed-host acceptance."""

from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import campaign, continuation_assessment as ca


class CampaignLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-campaign-lifecycle-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".saipen").mkdir()
        self.ctrl = campaign.CampaignController(self.root)
        authorization = {
            "authorized_scopes": sorted(campaign.ALL_SCOPES),
            "goal_binding": {"goal_ingress": "unit-goal", "authority_source": "E-1"},
            "resource_budget": {
                "max_generations": 1000,
                "max_cycles": 1000,
                "max_wall_seconds": 200000,
            },
        }
        self.enterContext(
            mock.patch.object(
                campaign.campaign_authority,
                "read_carrier",
                return_value={"authorization": authorization},
            )
        )
        self.grant = self.enterContext(
            mock.patch.object(
                campaign,
                "verify_operator_grant",
                return_value={
                    "valid": True,
                    "authorized_scopes": set(campaign.ALL_SCOPES),
                    "grant": {"reference": "unit-grant"},
                    "grant_digest": "a" * 64,
                },
            )
        )
        self.assess = self.enterContext(
            mock.patch.object(
                ca,
                "assess_continuation",
                return_value={
                    "classification": ca.ACTIVE_WORK,
                    "next_action": "PHASE BUILD T-1",
                },
            )
        )

    def admit(self, **kwargs):
        return self.ctrl.admit_campaign(
            campaign_id="CAMP-LIFECYCLE",
            authority_proof_reference="unit-grant",
            **kwargs,
        )

    def raw(self):
        return campaign.campaign_state_path(self.root).read_bytes()

    def test_incompatible_schemas_never_overwritten(self):
        path = campaign.campaign_state_path(self.root)
        path.parent.mkdir(parents=True)
        for version in (0, 2, 999, True):
            with self.subTest(version=version):
                body = json.dumps(
                    {
                        "schema_version": version,
                        "campaign_id": "old",
                        "campaign_state": campaign.ADMITTED,
                    }
                ).encode()
                path.write_bytes(body)
                for force in (False, True):
                    result = self.admit(force_new=force)
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(result["code"], campaign.STATE_INCOMPATIBLE)
                    self.assertEqual(self.raw(), body)
                self.assertFalse(self.ctrl.cancel()["ok"])
                self.assertEqual(self.raw(), body)

    def test_corruption_never_becomes_absence(self):
        path = campaign.campaign_state_path(self.root)
        path.parent.mkdir(parents=True)
        for body in (b"", b"{", b"[]", b"\xff", b'{"schema_version":1}'):
            with self.subTest(body=body):
                path.write_bytes(body)
                self.assertFalse(self.admit(force_new=True)["ok"])
                self.assertEqual(self.raw(), body)

    def test_directory_at_state_path_is_not_absence(self):
        campaign.campaign_state_path(self.root).mkdir(parents=True)
        self.assertEqual(
            campaign.inspect_campaign_state(self.root)["status"], campaign.STATE_CORRUPT
        )
        self.assertFalse(self.admit()["ok"])

    def test_unknown_lifecycle_state_is_corrupt(self):
        path = campaign.campaign_state_path(self.root)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({"schema_version": 1, "campaign_id": "old", "campaign_state": "MYSTERY"}),
            encoding="utf-8",
        )
        before = self.raw()
        self.assertFalse(self.admit()["ok"])
        self.assertEqual(self.raw(), before)

    def test_invalid_persisted_counters_and_attempt_shape_refuse_without_writes(self):
        self.admit()
        original = campaign.load_campaign_state(self.root)
        cases = [
            (key, value)
            for key in (
                "worker_generation",
                "cycle_count",
                "cancellation_epoch",
                "retry_count",
                "no_progress_count",
            )
            for value in (-1, "bad", True, [])
        ]
        cases += [("resource_budget", []), ("worker_attempt", []), ("worker_attempt", "bad")]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                state = dict(original, **{key: value})
                campaign.save_campaign_state(self.root, state)
                before = self.raw()
                worker = mock.Mock()
                result = self.ctrl.step(worker_func=worker)
                self.assertFalse(result["ok"])
                self.assertEqual(result["code"], campaign.STATE_CORRUPT)
                worker.assert_not_called()
                self.assertEqual(self.raw(), before)
                self.assertFalse(self.ctrl.cancel()["ok"])
                self.assertEqual(self.raw(), before)

    def test_existing_valid_campaign_resumes_without_writes(self):
        self.assertTrue(self.admit()["admitted"])
        before = self.raw()
        result = self.admit()
        self.assertEqual(result["status"], "RESUMED_EXISTING")
        self.assertEqual(self.raw(), before)

    def test_no_grant_creates_only_proposal(self):
        result = self.ctrl.admit_campaign()
        self.assertEqual(result["status"], campaign.PROPOSED)
        worker = mock.Mock()
        self.assertFalse(self.ctrl.step(worker_func=worker)["ok"])
        worker.assert_not_called()

    def test_completed_and_cancelled_states_are_immutable_under_cancel(self):
        self.admit()
        for terminal in (campaign.COMPLETE, campaign.CANCELLED):
            with self.subTest(terminal=terminal):
                state = campaign.load_campaign_state(self.root)
                state["campaign_state"] = terminal
                state["last_verified_result"] = {"receipt": "retained-original"}
                campaign.save_campaign_state(self.root, state)
                before = self.raw()
                for _ in range(2):
                    result = self.ctrl.cancel(reason="repeat")
                    self.assertEqual(result["status"], terminal)
                    self.assertEqual(self.raw(), before)
                self.assertEqual(campaign.CampaignController(self.root).step()["status"], terminal)

    def test_active_campaign_cancel_is_durable_and_once_only(self):
        self.admit()
        result = self.ctrl.cancel(reason="operator-stop")
        self.assertEqual(result["status"], campaign.CANCELLED)
        self.assertEqual(result["state"]["cancellation_epoch"], 1)
        before = self.raw()
        self.assertEqual(
            campaign.CampaignController(self.root).cancel()["status"], campaign.CANCELLED
        )
        self.assertEqual(self.raw(), before)

    def test_force_new_never_replaces_nonterminal_campaign(self):
        self.admit()
        for phase in campaign.CAMPAIGN_STATES - {campaign.COMPLETE, campaign.CANCELLED}:
            with self.subTest(phase=phase):
                state = campaign.load_campaign_state(self.root)
                state["campaign_state"] = phase
                campaign.save_campaign_state(self.root, state)
                before = self.raw()
                result = self.ctrl.admit_campaign(campaign_id="NEW", force_new=True)
                self.assertFalse(result["ok"], result)
                self.assertEqual(self.raw(), before)

    def test_terminal_replacement_retains_exact_original_bytes(self):
        self.admit()
        self.ctrl.cancel()
        before = self.raw()
        result = self.ctrl.admit_campaign(campaign_id="NEW")
        self.assertTrue(result["ok"], result)
        self.assertEqual(
            (self.root / result["state"]["predecessor_reference"]).read_bytes(), before
        )

    def test_invalid_replacement_grant_changes_nothing(self):
        self.admit()
        self.grant.return_value = {"valid": False, "status": "REVOKED"}
        before = self.raw()
        result = self.ctrl.admit_campaign(
            campaign_id="NEW", force_new=True, authority_proof_reference="revoked"
        )
        self.assertFalse(result["ok"])
        self.assertEqual(self.raw(), before)

    def test_closed_positive_finite_budget_dimensions(self):
        cases = [
            {key: value}
            for key in ("max_cycles", "max_generations", "max_wall_seconds")
            for value in (-1, 0, True, float("nan"), float("inf"), "2", None)
        ] + [{"max_cycles": 1.5}, {"max_generations": 1.5}, {"unknown": 1}]
        for budget in cases:
            with self.subTest(budget=budget):
                result = self.admit(resource_budget=budget)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["code"], "INVALID_RESOURCE_BUDGET")
                self.assertFalse(campaign.campaign_state_path(self.root).exists())
        for budget in ([], [1], "bad", 1):
            with self.subTest(budget=budget):
                self.assertFalse(self.admit(resource_budget=budget)["ok"])

    def test_invalid_horizon_never_throws(self):
        for horizon in ("UNKNOWN", [], None):
            with self.subTest(horizon=horizon):
                self.assertEqual(self.admit(horizon=horizon)["code"], "INVALID_HORIZON")

    def test_max_cycles_survives_restart_and_is_not_completion(self):
        self.admit(resource_budget={"max_cycles": 1, "max_generations": 10})
        worker = mock.Mock(return_value={"ok": True})
        self.assertTrue(self.ctrl.step(worker_func=worker)["ok"])
        result = campaign.CampaignController(self.root).step(worker_func=worker)
        self.assertEqual(result["event"], "BUDGET_EXHAUSTED")
        self.assertEqual(result["reason"], "max_cycles")
        self.assertNotEqual(result["state"]["campaign_state"], campaign.COMPLETE)
        self.assertEqual(worker.call_count, 1)

    def test_durable_intent_precedes_worker_execution(self):
        self.admit()

        def worker(root, generation):
            state = campaign.load_campaign_state(root)
            attempt = state["worker_attempt"]
            self.assertEqual(attempt["generation"], generation)
            self.assertEqual(attempt["campaign_id"], state["campaign_id"])
            self.assertEqual(attempt["status"], "EXECUTOR_STARTED")
            self.assertTrue(attempt["attempt_id"])
            self.assertTrue(attempt["execution_intent"])
            return {"ok": True}

        result = self.ctrl.step(worker_func=worker)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"]["worker_attempt"]["status"], "EXECUTION_RESULT_OBSERVED")

    def test_worker_exception_is_unknown_outcome_and_never_blindly_retried(self):
        self.admit()
        worker = mock.Mock(side_effect=RuntimeError("side effect may already exist"))
        result = self.ctrl.step(worker_func=worker)
        self.assertFalse(result["ok"])
        attempt = result["state"]["worker_attempt"]
        self.assertEqual(attempt["status"], "UNKNOWN_OUTCOME")
        self.assertIn("side effect", attempt["error"])
        self.assertEqual(result["state"]["retry_count"], 1)
        retry = campaign.CampaignController(self.root).step(worker_func=worker)
        self.assertEqual(retry["code"], "ATTEMPT_RECOVERY_REQUIRED")
        self.assertEqual(retry["state"]["worker_attempt"]["attempt_id"], attempt["attempt_id"])
        self.assertEqual(worker.call_count, 1)
        self.assertEqual(self.ctrl.cancel()["status"], campaign.CANCELLED)

    def test_internal_typeerror_does_not_invoke_worker_three_times(self):
        self.admit()
        calls = []

        def worker(root, generation=None):
            calls.append(generation)
            raise TypeError("error after side effect")

        result = self.ctrl.step(worker_func=worker)
        self.assertFalse(result["ok"])
        self.assertEqual(calls, [1])

    def test_positional_and_root_only_workers_remain_supported(self):
        self.admit()
        for worker in (lambda root, gen: {"ok": True}, lambda root: {"ok": True}):
            self.assertTrue(self.ctrl.step(worker_func=worker)["ok"])

    def test_forensic_backend_failures_never_become_quiescent_success(self):
        for status, expected in (
            ("ANALYSIS_BLOCKED", campaign.EXTERNAL_BLOCKED),
            ("RETRYABLE_FAILURE", campaign.RETRY_WAIT),
            ("AUTHORITY_REQUIRED", campaign.AUTHORITY_BLOCKED),
            ("LOG_CORRUPT", campaign.EXTERNAL_BLOCKED),
        ):
            with self.subTest(status=status):
                state_path = campaign.campaign_state_path(self.root)
                if state_path.exists():
                    state_path.unlink()
                self.admit()
                state = campaign.load_campaign_state(self.root)
                state["authority_scope"] = campaign.FORENSIC_ANALYSIS_SCOPE
                campaign.save_campaign_state(self.root, state)
                self.assess.return_value = {"classification": ca.MAINTENANCE_AVAILABLE}
                failure = {"ok": False, "status": status, "error": "original backend diagnosis"}
                with mock.patch.object(
                    self.ctrl.saipal, "discover", return_value=failure
                ), mock.patch.object(
                    self.ctrl.saipal,
                    "deliver_finding_to_audit_inbox",
                ) as delivery:
                    result = self.ctrl.step()
                self.assertFalse(result["ok"])
                self.assertEqual(result["event"], "FORENSIC_DISCOVERY_FAILED")
                self.assertEqual(result["status"], status)
                self.assertEqual(result["state"]["campaign_state"], expected)
                self.assertEqual(result["state"]["last_saipal_generation"], 0)
                delivery.assert_not_called()

    def test_interrupted_generation_preserves_identity_across_restart(self):
        self.admit()
        with self.assertRaises(KeyboardInterrupt):
            self.ctrl.step(worker_func=mock.Mock(side_effect=KeyboardInterrupt))
        before = campaign.load_campaign_state(self.root)["worker_attempt"]
        worker = mock.Mock()
        result = campaign.CampaignController(self.root).step(worker_func=worker)
        self.assertEqual(result["code"], "ATTEMPT_RECOVERY_REQUIRED")
        self.assertEqual(result["state"]["worker_attempt"]["attempt_id"], before["attempt_id"])
        worker.assert_not_called()

    def test_process_death_preserves_attempt_and_releases_lifecycle_lock(self):
        self.admit()
        script = """
import os,sys
from unittest.mock import patch
from saipen_engine import campaign, continuation_assessment as ca
grant={'valid':True,'grant_digest':'a'*64,'authorized_scopes':set(campaign.ALL_SCOPES)}
with patch.object(campaign,'verify_operator_grant',return_value=grant), \\
     patch.object(ca,'assess_continuation',return_value={'classification':ca.ACTIVE_WORK}):
    campaign.CampaignController(sys.argv[1]).step(worker_func=lambda root, generation: os._exit(17))
"""
        env = dict(os.environ, PYTHONPATH=str(Path(campaign.__file__).resolve().parents[1]))
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, str(self.root)],
            capture_output=True,
            timeout=10,
            env=env,
        )
        self.assertEqual(result.returncode, 17, result.stderr)
        attempt = campaign.load_campaign_state(self.root)["worker_attempt"]
        self.assertEqual(attempt["status"], "EXECUTOR_STARTED")
        result = self.ctrl.step(worker_func=mock.Mock())
        self.assertEqual(result["code"], "ATTEMPT_RECOVERY_REQUIRED")
        self.assertEqual(self.ctrl.cancel()["status"], campaign.CANCELLED)

    def test_completed_worker_result_recovers_after_commit_lock_contention(self):
        self.admit()
        held = []

        def worker(root, generation):
            held.append(self.ctrl._acquire_lock())
            return {"ok": True, "result_identity": "original-result"}

        try:
            result = self.ctrl.step(worker_func=worker)
            self.assertEqual(result["code"], "ATTEMPT_RECOVERY_REQUIRED")
        finally:
            for lk in held:
                lk.release()
        attempt = campaign.load_campaign_state(self.root)["worker_attempt"]
        unused_worker = mock.Mock()
        result = campaign.CampaignController(self.root).step(worker_func=unused_worker)
        self.assertEqual(result["event"], "WORKER_ATTEMPT_RECONCILED")
        self.assertEqual(result["state"]["worker_attempt"]["attempt_id"], attempt["attempt_id"])
        self.assertEqual(result["worker_result"]["result_identity"], "original-result")
        unused_worker.assert_not_called()
        self.assertTrue(self.ctrl.step(worker_func=lambda root: {"ok": True})["ok"])
        self.assertEqual(campaign.load_campaign_state(self.root)["worker_generation"], 2)

    def test_altered_attempt_receipt_never_becomes_a_success(self):
        self.admit()
        held = []

        def worker(root, generation):
            held.append(self.ctrl._acquire_lock())
            return {"ok": True}

        try:
            self.ctrl.step(worker_func=worker)
        finally:
            for lk in held:
                lk.release()
        state = campaign.load_campaign_state(self.root)
        outcome = self.root / state["worker_attempt"]["result_reference"]
        outcome.write_bytes(b'{"ok":true}')
        before = self.raw()
        worker = mock.Mock()
        result = self.ctrl.step(worker_func=worker)
        self.assertEqual(result["code"], "ATTEMPT_RESULT_CORRUPT")
        self.assertEqual(self.raw(), before)
        worker.assert_not_called()

    def test_incomplete_outcome_envelope_is_a_typed_refusal(self):
        self.admit()
        held = []

        def worker(root, generation):
            held.append(self.ctrl._acquire_lock())
            return {"ok": True}

        try:
            self.ctrl.step(worker_func=worker)
        finally:
            for lk in held:
                lk.release()
        state = campaign.load_campaign_state(self.root)
        path = self.root / state["worker_attempt"]["result_reference"]
        outcome = json.loads(path.read_text(encoding="utf-8"))
        outcome.pop("observed_at")
        outcome["receipt_digest"] = campaign._outcome_digest(outcome)
        path.write_text(json.dumps(outcome), encoding="utf-8")
        before = self.raw()
        result = self.ctrl.step(worker_func=mock.Mock())
        self.assertEqual(result["code"], "ATTEMPT_RESULT_CORRUPT")
        self.assertEqual(self.raw(), before)

    def test_cancel_and_parallel_step_while_worker_is_running(self):
        self.admit()
        entered, release = threading.Event(), threading.Event()

        def worker(root, generation):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test worker was not released")
            return {"ok": True, "progress_verified": True}

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.ctrl.step, worker_func=worker)
            self.addCleanup(release.set)
            try:
                self.assertTrue(entered.wait(3))
                duplicate = mock.Mock()
                result = campaign.CampaignController(self.root).step(worker_func=duplicate)
                self.assertEqual(result["code"], "ATTEMPT_RECOVERY_REQUIRED")
                duplicate.assert_not_called()
                stopped = campaign.CampaignController(self.root).cancel()
                self.assertEqual(stopped["status"], campaign.CANCELLED)
                stopped_bytes = self.raw()
            finally:
                release.set()
            late = future.result(timeout=3)
        self.assertFalse(late["ok"])
        self.assertEqual(late["code"], "WORKER_GENERATION_FENCED")
        self.assertEqual(self.raw(), stopped_bytes)

    def test_late_worker_cannot_overwrite_new_campaign(self):
        self.admit()

        def worker(root, generation):
            self.ctrl.cancel()
            self.ctrl.admit_campaign(campaign_id="NEW")
            return {"ok": True}

        result = self.ctrl.step(worker_func=worker)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "WORKER_GENERATION_FENCED")
        self.assertEqual(campaign.load_campaign_state(self.root)["campaign_id"], "NEW")


if __name__ == "__main__":
    unittest.main()
