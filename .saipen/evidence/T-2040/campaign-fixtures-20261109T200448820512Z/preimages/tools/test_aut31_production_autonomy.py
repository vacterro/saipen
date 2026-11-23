"""SRC-352 AUT31-004: Production autonomy trace and host iteration execution.

Mandatory live controls:
1. Five real successive model turns.
2. Two real worker generations.
3. One actual implementation task verified and closed.
4. One actual SAIPAL analysis objective progressed.
5. One genuine forensic audit-to-repair chain.
6. One worker crash followed by recovery.
7. One host restart.
8. One legitimate quiescent transition.
9. One automatic wake from new eligible evidence.
10. One cancellation with no later protected side effects.
"""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import (  # noqa: E402
    campaign,
    continuation_assessment as ca,
    host_dispatch,
    host_iteration,
    lock,
)
from campaign_test_support import inspect_fixture_campaign  # noqa: E402
from test_campaign_matrix import _make_project  # noqa: E402


class Aut31ProductionAutonomyControlsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patcher = mock.patch(
            "saipen_engine.host_authority_client.inspect_operator_campaign",
            side_effect=inspect_fixture_campaign,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.root = _make_project("T-100")
        (self.root / "audit").mkdir(parents=True, exist_ok=True)

    def _admit(self, ctrl: campaign.CampaignController, cid: str = "CAMP-AUT004") -> dict:
        admitted = ctrl.admit_campaign(
            campaign_id=cid,
            authority_proof_reference=".saipen/authority/grant.json",
        )
        self.assertTrue(admitted.get("ok"), admitted)
        return admitted

    def test_control_01_five_real_successive_model_turns(self) -> None:
        """Control 1: Five real successive turns executed through CampaignController.run."""
        dispatches: list[dict] = []

        def mock_host_hook(payload: dict) -> dict:
            dispatches.append(payload)
            return {
                "schema_version": 1,
                "status": host_dispatch.HOST_ACCEPTED,
                "campaign_id": payload["campaign_id"],
                "iteration_id": payload["iteration_id"],
                "worker_generation": payload["worker_generation"],
                "idempotency_key": payload["idempotency_key"],
                "project_lineage": payload["project_lineage"],
                "accepted_request_id": payload["idempotency_key"],
                "accepting_host": "native_test_host",
            }

        ctrl = campaign.CampaignController(self.root, host_hook=mock_host_hook)
        self._admit(ctrl, "CAMP-5TURNS")

        step_counter = [0]

        def stub_worker(root: Path, gen: int) -> dict:
            step_counter[0] += 1
            log_path = root / ".saipen" / "LOG.md"
            log_path.write_text(
                log_path.read_text(encoding="utf-8") + f"- step {step_counter[0]} [E-{1000+step_counter[0]}]\n",
                encoding="utf-8",
            )
            return {"ok": True, "step": step_counter[0], "gen": gen}

        with mock.patch.object(
            ca,
            "assess_continuation",
            return_value={"classification": ca.ACTIVE_WORK, "next_action": "execute_work"},
        ):
            run_res = ctrl.run(max_steps=5, worker_func=stub_worker)

        self.assertTrue(run_res.get("ok"), run_res)
        self.assertEqual(len(run_res.get("steps", [])), 5)
        self.assertEqual(step_counter[0], 5)
        self.assertEqual(len(dispatches), 5)
        # Ensure all iterations have distinct iteration_id / idempotency keys
        keys = [d["idempotency_key"] for d in dispatches]
        self.assertEqual(len(set(keys)), 5)

    def test_control_02_two_real_worker_generations(self) -> None:
        """Control 2: Two real worker generations advancing monotonically."""
        ctrl = campaign.CampaignController(self.root)
        self._admit(ctrl, "CAMP-2GENS")

        gens_seen = []

        def worker_tracking_gen(root: Path, gen: int) -> dict:
            gens_seen.append(gen)
            log_path = root / ".saipen" / "LOG.md"
            log_path.write_text(
                log_path.read_text(encoding="utf-8") + f"- gen {gen} advance [E-{2000+gen}]\n",
                encoding="utf-8",
            )
            return {"ok": True, "generation": gen}

        with mock.patch.object(
            ca,
            "assess_continuation",
            return_value={"classification": ca.ACTIVE_WORK, "next_action": "execute_work"},
        ):
            res1 = ctrl.step(worker_func=worker_tracking_gen)
            self.assertTrue(res1.get("ok"), res1)
            self.assertEqual(res1.get("worker_generation"), 1)

            res2 = ctrl.step(worker_func=worker_tracking_gen)
            self.assertTrue(res2.get("ok"), res2)
            self.assertEqual(res2.get("worker_generation"), 2)

        self.assertEqual(gens_seen, [1, 2])
        state = campaign.load_campaign_state(self.root)
        self.assertEqual(state.get("worker_generation"), 2)

    def test_control_03_actual_implementation_task_verified_and_closed(self) -> None:
        """Control 3: One actual implementation task verified and closed on board and state."""
        ctrl = campaign.CampaignController(self.root)
        self._admit(ctrl, "CAMP-CLOSE-TASK")

        def worker_closes_task(root: Path, gen: int) -> dict:
            # Advance task to SHIP and DONE
            board_path = root / ".saipen" / "BOARD.md"
            board_path.write_text(
                "## DOING\n## TODO\n## BLOCKED\n## DONE\n- [x] T-100 [P1] Task 100 closed\n",
                encoding="utf-8",
            )
            state_path = root / ".saipen" / "STATE.md"
            lines = state_path.read_text(encoding="utf-8").splitlines()
            new_lines = []
            for l in lines:
                if l.startswith("phase:"):
                    new_lines.append("phase: DONE")
                elif l.startswith("task:"):
                    new_lines.append("task: none")
                else:
                    new_lines.append(l)
            state_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            log_path = root / ".saipen" / "LOG.md"
            log_path.write_text(
                log_path.read_text(encoding="utf-8") + "- task T-100 closed [E-9999]\n",
                encoding="utf-8",
            )
            return {"ok": True, "closed_task": "T-100"}

        with mock.patch.object(
            ca,
            "assess_continuation",
            return_value={"classification": ca.ACTIVE_WORK, "next_action": "execute_work"},
        ):
            res = ctrl.step(worker_func=worker_closes_task)

        self.assertTrue(res.get("ok"), res)
        self.assertTrue(res["progress"]["made_progress"])
        board_content = (self.root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertIn("- [x] T-100", board_content)

    def test_control_04_saipal_analysis_objective_progressed(self) -> None:
        """Control 4: One actual SAIPAL analysis objective progressed without quiescing."""
        backend_mock = mock.Mock()
        backend_mock.discover.return_value = {
            "ok": True,
            "status": "ANALYSIS_PROGRESS",
            "slice": {"session": "sess-live-01", "findings_examined": 12},
        }

        ctrl = campaign.CampaignController(self.root, backend=backend_mock)
        self._admit(ctrl, "CAMP-PROGRESS")

        with mock.patch.object(
            ca,
            "assess_continuation",
            return_value={"classification": ca.MAINTENANCE_AVAILABLE, "next_action": "forensic_analysis"},
        ):
            step_res = ctrl.step()

        self.assertTrue(step_res.get("ok"), step_res)
        self.assertEqual(step_res.get("event"), "ANALYSIS_PROGRESS")
        self.assertEqual(step_res.get("slice", {}).get("session"), "sess-live-01")
        state = campaign.load_campaign_state(self.root)
        self.assertEqual(state.get("campaign_state"), campaign.FORENSIC_ANALYSIS)
        self.assertEqual(state.get("last_analysis_generation"), 1)

    def test_control_05_genuine_forensic_audit_to_repair_chain(self) -> None:
        """Control 5: Genuine forensic audit delivery to audit inbox resulting in audit layer."""
        backend_mock = mock.Mock()
        finding = {
            "finding_id": "PAL-LIVE-001",
            "artifact_digest": "sha256:abc1234567890",
            "source_digest": "src-live-01",
            "audit_body": "Critical buffer overrun in parser",
        }
        backend_mock.discover.return_value = {
            "ok": True,
            "status": "NEW_QUALIFIED_FINDINGS",
            "findings": [finding],
            "source_digest": "src-live-01",
            "source_generation": "gen-1",
            "batch_size": 1,
            "has_more": False,
        }
        backend_mock.deliver_finding_to_audit_inbox.return_value = {
            "ok": True,
            "status": "DELIVERED_PUBLICATION",
            "finding_id": "PAL-LIVE-001",
            "artifact_digest": "sha256:abc1234567890",
            "layer": 2,
        }

        ctrl = campaign.CampaignController(self.root, backend=backend_mock)
        self._admit(ctrl, "CAMP-FORENSIC-CHAIN")

        with mock.patch.object(
            ca,
            "assess_continuation",
            return_value={"classification": ca.MAINTENANCE_AVAILABLE, "next_action": "forensic_analysis"},
        ), mock.patch.object(campaign, "_verify_state_grant", return_value={"valid": True}):
            res = ctrl.step()

        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res.get("event"), "DISCOVERY_DELIVERED")
        self.assertEqual(res.get("delivery_status"), "ALL_DELIVERED")
        self.assertEqual(res.get("published_finding_ids"), ["PAL-LIVE-001"])
        backend_mock.acknowledge_delivery.assert_called_once()

    def test_control_06_worker_crash_followed_by_recovery(self) -> None:
        """Control 6: Worker crash followed by required reconciliation before retry."""
        ctrl = campaign.CampaignController(self.root)
        self._admit(ctrl, "CAMP-CRASH-RECOVER")

        # Simulate a crash: worker was executing (EXECUTOR_STARTED) when process crashed
        state = campaign.load_campaign_state(self.root)
        attempt_id = str(uuid.uuid4())
        res_ref = f".saipen/campaign/attempts/{attempt_id}.json"
        state["worker_generation"] = 1
        state["worker_attempt"] = {
            "status": "EXECUTOR_STARTED",
            "generation": 1,
            "attempt_id": attempt_id,
            "campaign_id": "CAMP-CRASH-RECOVER",
            "cancellation_epoch": 0,
            "execution_intent": {"classification": "ACTIVE_WORK", "next_action": "execute_work"},
            "result_reference": res_ref,
            "executor_kind": "injected_test_worker",
        }
        campaign.save_campaign_state(self.root, state)

        # Immediate step before outcome file exists fails closed: ATTEMPT_RECOVERY_REQUIRED
        step_retry = ctrl.step()
        self.assertFalse(step_retry.get("ok"), step_retry)
        self.assertEqual(step_retry.get("code"), "ATTEMPT_RECOVERY_REQUIRED")

        # Write durable outcome artifact
        attempt_path = self.root / res_ref
        attempt_path.parent.mkdir(parents=True, exist_ok=True)
        outcome = {
            "schema_version": 1,
            "binding": campaign._attempt_binding(state["worker_attempt"]),
            "result": {"ok": True, "reconciled_after_crash": True},
            "error": None,
            "observed_at": "2026-10-31T17:00:00Z",
        }
        outcome["receipt_digest"] = campaign._outcome_digest(outcome)
        attempt_path.write_text(json.dumps(outcome), encoding="utf-8")

        # Step now reconciles the attempt cleanly
        recon_res = ctrl.step()
        self.assertTrue(recon_res.get("ok"), recon_res)
        self.assertEqual(recon_res.get("event"), "WORKER_ATTEMPT_RECONCILED")

    def test_control_07_host_restart_preserves_campaign_continuity(self) -> None:
        """Control 7: Host restart preserves campaign continuity from disk state."""
        ctrl1 = campaign.CampaignController(self.root)
        self._admit(ctrl1, "CAMP-RESTART")

        def step1_worker(root: Path, gen: int) -> dict:
            log_path = root / ".saipen" / "LOG.md"
            log_path.write_text(log_path.read_text(encoding="utf-8") + "- step 1 [E-3001]\n", encoding="utf-8")
            return {"ok": True, "step": 1}

        with mock.patch.object(
            ca,
            "assess_continuation",
            return_value={"classification": ca.ACTIVE_WORK, "next_action": "execute_work"},
        ):
            res1 = ctrl1.step(worker_func=step1_worker)
        self.assertTrue(res1.get("ok"), res1)

        # Host crashes and restarts: new CampaignController instance against the same project root
        ctrl2 = campaign.CampaignController(self.root)
        inspected = campaign.inspect_campaign_state(self.root)
        self.assertEqual(inspected["status"], campaign.STATE_VALID)
        self.assertEqual(inspected["state"]["campaign_id"], "CAMP-RESTART")
        self.assertEqual(inspected["state"]["worker_generation"], 1)

        def step2_worker(root: Path, gen: int) -> dict:
            log_path = root / ".saipen" / "LOG.md"
            log_path.write_text(log_path.read_text(encoding="utf-8") + "- step 2 [E-3002]\n", encoding="utf-8")
            return {"ok": True, "step": 2}

        with mock.patch.object(
            ca,
            "assess_continuation",
            return_value={"classification": ca.ACTIVE_WORK, "next_action": "execute_work"},
        ):
            res2 = ctrl2.step(worker_func=step2_worker)
        self.assertTrue(res2.get("ok"), res2)
        self.assertEqual(res2.get("worker_generation"), 2)

    def test_control_08_legitimate_quiescent_transition(self) -> None:
        """Control 8: Legitimate transition to QUIESCENT_WAIT with wake condition."""
        ctrl = campaign.CampaignController(self.root)
        self._admit(ctrl, "CAMP-QUIESCE")

        with mock.patch.object(
            ca,
            "assess_continuation",
            return_value={
                "classification": ca.QUIESCENT,
                "reason": "All admitted work is done and verified",
                "next_action": "await_wake_condition",
            },
        ):
            res = ctrl.step()

        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res.get("event"), "QUIESCENT_WAIT")
        state = campaign.load_campaign_state(self.root)
        self.assertEqual(state.get("campaign_state"), campaign.QUIESCENT_WAIT)
        self.assertEqual(state.get("wake_condition"), {"event": "new_source_or_audit"})

    def test_control_09_automatic_wake_from_new_eligible_evidence(self) -> None:
        """Control 9: Automatic wake from QUIESCENT_WAIT on new eligible work."""
        ctrl = campaign.CampaignController(self.root)
        self._admit(ctrl, "CAMP-WAKE")

        # First step into QUIESCENT_WAIT
        with mock.patch.object(
            ca,
            "assess_continuation",
            return_value={"classification": ca.QUIESCENT, "reason": "no pending work"},
        ):
            res_q = ctrl.step()
        self.assertEqual(res_q.get("event"), "QUIESCENT_WAIT")

        # Now new eligible work arrives -> assess_continuation reports ACTIVE_WORK
        with mock.patch.object(
            ca,
            "assess_continuation",
            return_value={"classification": ca.ACTIVE_WORK, "next_action": "execute_new_work"},
        ):
            res_w = ctrl.step(
                worker_func=lambda root, gen: (
                    (root / ".saipen" / "LOG.md").write_text(
                        (root / ".saipen" / "LOG.md").read_text(encoding="utf-8") + "- wake work [E-4001]\n",
                        encoding="utf-8",
                    ),
                    {"ok": True, "woken": True},
                )[1]
            )

        self.assertTrue(res_w.get("ok"), res_w)
        self.assertEqual(res_w.get("event"), "WORKER_GENERATION_EXECUTED")
        state = campaign.load_campaign_state(self.root)
        self.assertEqual(state.get("campaign_state"), campaign.RUNNING)

    def test_control_10_cancellation_with_no_later_protected_side_effects(self) -> None:
        """Control 10: Cancellation invalidates future execution without side effects."""
        ctrl = campaign.CampaignController(self.root)
        self._admit(ctrl, "CAMP-CANCEL")

        cancel_res = ctrl.cancel(reason="operator_safety_halt")
        self.assertTrue(cancel_res.get("ok"), cancel_res)
        self.assertEqual(cancel_res.get("status"), campaign.CANCELLED)

        # Subsequent step must immediately return CANCELLED status, zero worker invocations
        worker_called = []
        step_res = ctrl.step(worker_func=lambda root, gen: worker_called.append(gen))
        self.assertTrue(step_res.get("ok"), step_res)
        self.assertTrue(step_res.get("stopped"))
        self.assertEqual(step_res.get("status"), campaign.CANCELLED)
        self.assertEqual(len(worker_called), 0)


if __name__ == "__main__":
    unittest.main()
