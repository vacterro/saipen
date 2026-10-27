"""Comprehensive campaign integration regression test matrix C01-C40 (Block 10).

Covers functional matrix, negative defect controls (NEG01-NEG09),
and contracts modeled on production gates (A-L). Native acceptance is not inferred.
"""

from __future__ import annotations

import concurrent.futures
import datetime as _dt
import hashlib
import json
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from campaign_test_support import (
    inspect_fixture_campaign,
    write_qualification_artifact,
    write_scoped_fixture_grant,
    write_verification_receipt,
)

from saipen_engine import (
    audit_enqueue,
    campaign,
    continuation_assessment as ca,
    host_dispatch,
    host_iteration,
    iteration,
    lock,
    saipal_adapter,
    supervisor,
    watchdog,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_STATE = (REPO_ROOT / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")


def _seat_state(text: str, **fields) -> str:
    for key, value in fields.items():
        line = f"{key}: {value}"
        if re.search(rf"(?m)^{key}:.*$", text):
            text = re.sub(rf"(?m)^{key}:.*$", line, text)
        else:
            close = text.index("\n---", 3)
            text = text[:close] + "\n" + line + text[close:]
    return text


def _make_project(task="T-100", *, with_grant: bool = True) -> Path:
    root = Path(tempfile.mkdtemp(prefix="saipen-camp-mat-"))
    (root / ".saipen").mkdir(parents=True, exist_ok=True)
    state_txt = _seat_state(
        REAL_STATE,
        phase="BUILD",
        task=task,
        next_action=f'"PHASE BUILD {task}"',
        blocker="none",
        transition_from="SCOUT",
        execution_intent="goal",
        goal_tickets=5,
        goal_waves=0,
    )
    (root / ".saipen" / "STATE.md").write_text(state_txt, encoding="utf-8")
    (root / ".saipen" / "BOARD.md").write_text(
        f"## DOING\n- [/] {task} [P1] Task 100\n## TODO\n## BLOCKED\n## DONE\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "LOG.md").write_text("# LOG\n", encoding="utf-8")
    lineage = "lineage-0123456789abcdef0123456789abcdef"
    (root / ".saipen" / "IDENTITY.md").write_text(
        f"---\nproject_lineage: {lineage}\n---\n",
        encoding="utf-8",
    )
    if with_grant:
        write_scoped_fixture_grant(root)
    return root


class TestCampaignMatrix(unittest.TestCase):
    """INTEGRATION: Comprehensive campaign integration regression test matrix C01-C40."""
    CATEGORY = "INTEGRATION"

    def setUp(self):
        self._patcher = mock.patch(
            "saipen_engine.host_authority_client.inspect_operator_campaign",
            side_effect=inspect_fixture_campaign,
        )
        self._patcher.start()
        # AUT-001: this suite covers INTEGRATION mechanics, not host trust. The
        # receipts below are dicts this process wrote, which the production
        # validator now refuses because no live authority broker reproduces
        # them. The simulation is declared HERE, once, instead of being smuggled
        # in through receipt shape: host trust has its own module.
        self._trust_patcher = mock.patch(
            "saipen_engine.host_dispatch._broker_verified_receipt",
            return_value=True,
        )
        self._trust_patcher.start()

    def tearDown(self):
        self._trust_patcher.stop()
        self._patcher.stop()

    def test_c05_model_final_response_dispatches_next_turn(self):
        root = _make_project()
        ctrl = host_iteration.HostIterationController(
            required={"filesystem", "git"},
            project_root=root,
        )
        verdict = {
            "decision": iteration.AUTO_KICK,
            "canonical_task": "T-100",
            "phase": "BUILD",
            "route_reason": "active_work",
        }
        hook_called = []

        def mock_hook(payload):
            hook_called.append(payload)
            # CORE-004: a receipt without schema, lineage, accepting host and
            # accepted request identity cannot prove ANY dispatch, so the
            # controller must not report a confirmed turn from one.
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

        action = ctrl.on_model_turn_finished(
            verdict,
            turn_context={
                "project_root": root,
                "iteration_id": 1,
                "host_hook": mock_hook,
                "authority_proof_reference": ".saipen/authority/grant.json",
            },
        )
        self.assertEqual(action, host_iteration.KICK_NEXT_ITERATION)
        self.assertEqual(len(hook_called), 1)
        self.assertTrue(hook_called[0]["idempotency_key"])

    def test_c06_final_response_callback_delivered_twice_is_idempotent(self):
        root = _make_project()
        ctrl = host_iteration.HostIterationController(
            required={"filesystem", "git"},
            project_root=root,
        )
        verdict = {
            "decision": iteration.AUTO_KICK,
            "canonical_task": "T-100",
            "phase": "BUILD",
            "route_reason": "active_work",
        }
        turn_ctx = {"project_root": root, "iteration_id": 1, "worker_generation": 1}
        act1 = ctrl.on_model_turn_finished(verdict, turn_context=turn_ctx)
        act2 = ctrl.on_model_turn_finished(verdict, turn_context=turn_ctx)
        self.assertEqual(act1, host_iteration.KICK_NEXT_ITERATION)
        self.assertEqual(act2, host_iteration.KICK_NEXT_ITERATION)
        inbox = root / ".saipen" / "campaign" / "dispatch_inbox.jsonl"
        lines = [l for l in inbox.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(lines), 1, "Exactly one scheduled dispatch entry must exist")

    def test_c07_c08_host_dispatch_concurrency_and_idempotency_key(self):
        root = _make_project()
        invocations = []

        def counting_hook(payload):
            invocations.append(payload)
            time.sleep(0.02)
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

        payload = host_dispatch.build_dispatch_payload(
            root, campaign_id="CAMPAIGN-CONCURRENCY-TEST", worker_generation=1, iteration_id=1
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(host_dispatch.dispatch_next_turn, root, payload, host_hook=counting_hook, print_advisory=False)
            f2 = ex.submit(host_dispatch.dispatch_next_turn, root, payload, host_hook=counting_hook, print_advisory=False)
            res1 = f1.result()
            res2 = f2.result()

        self.assertEqual(len(invocations), 1, "Native hook must be called exactly once across concurrent callers")
        dispatched_count = sum(1 for r in (res1, res2) if r.get("dispatched") is True)
        self.assertEqual(dispatched_count, 1)

    def test_c09_c10_worker_cycles_slice_boundary_advances_generation(self):
        root = _make_project()
        c_ctrl = campaign.CampaignController(root)
        c_ctrl.admit_campaign(
            campaign_id="CAMP-CYCLE-TEST",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        worker = lambda r, g: {"progress_verified": True}
        res1 = c_ctrl.step(worker_func=worker)
        self.assertTrue(res1["ok"])
        st1 = campaign.load_campaign_state(root)
        self.assertEqual(st1["worker_generation"], 1)

        res2 = c_ctrl.step(worker_func=worker)
        self.assertTrue(res2["ok"])
        st2 = campaign.load_campaign_state(root)
        self.assertEqual(st2["worker_generation"], 2)

    def test_c11_worker_generation_lease_fencing(self):
        root = _make_project()
        lease = watchdog.acquire_lease(root, "worker-gen-1")
        self.assertEqual(lease["lease_generation"], 1)
        now_future = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=200)
        rep = supervisor.replace_worker(root, "worker-gen-2", now=now_future)
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["lease"]["lease_generation"], 2)
        self.assertFalse(watchdog.mutation_allowed(root, "worker-gen-1", 1, now=now_future))

    def test_c15_saipal_runtime_unavailable(self):
        adapter = saipal_adapter.SaipalAdapter(saipal_home=Path("V:/nonexistent_saipal_dir"))
        res = adapter.probe()
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], saipal_adapter.RUNTIME_UNAVAILABLE)

    def test_c16_c18_c19_c22_audit_enqueue_and_publication_authorization(self):
        root = _make_project()
        adapter = saipal_adapter.SaipalAdapter()
        body = "# Audit Finding PAL-9999\nTest defect reproduction\n"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        finding = {
            "finding_id": "PAL-9999",
            "state": "QUALIFIED",
            "drift_class": "COMMAND_ROUTE_DRIFT",
            "severity": "P1",
            "root_cause": "Test defect reproduction",
            "rule_ids": ["PAL-TEST-01"],
            "change_target": "ENGINE",
            "qualification_receipt": write_qualification_artifact(root, "QUAL-REC-PAL-9999"),
            "audit_body": body,
            "artifact_digest": digest,
        }
        res_staged = adapter.deliver_finding_to_audit_inbox(root, finding, publication_authorized=False)
        self.assertFalse(res_staged["ok"])
        self.assertEqual(res_staged["status"], saipal_adapter.STAGED_PUBLICATION)

        res_deliv = adapter.deliver_finding_to_audit_inbox(root, finding, publication_authorized=True)
        self.assertTrue(res_deliv["ok"])
        self.assertEqual(res_deliv["status"], saipal_adapter.DELIVERED_PUBLICATION)
        layer_num = res_deliv["receipt"]["layer"]
        self.assertTrue((root / "audit" / f"{layer_num}.md").is_file())

        res_dup = adapter.deliver_finding_to_audit_inbox(root, finding, publication_authorized=True)
        self.assertTrue(res_dup["ok"])
        self.assertEqual(res_dup["receipt"]["layer"], layer_num)
        self.assertTrue(res_dup["receipt"]["idempotent"])

    def test_c17_saipal_no_new_evidence_no_invented_findings(self):
        root = _make_project()
        adapter = saipal_adapter.SaipalAdapter()
        with mock.patch.object(adapter, "probe", return_value={"ok": True, "status": "BOUND"}), \
             mock.patch.object(adapter, "_run_cmd", return_value={"ok": True, "data": {"findings": [], "counts": {}}}):
            disc = adapter.discover(root)
            self.assertTrue(disc["ok"])
            self.assertEqual(disc["status"], saipal_adapter.NO_NEW_EVIDENCE)
            self.assertEqual(len(disc.get("findings", [])), 0)

    def test_c20_interrupted_audit_enqueue_crash_safe(self):
        root = _make_project()
        audit_dir = root / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = audit_dir / "1.tmp.99999"
        tmp_file.write_text("partial corrupted content", encoding="utf-8")
        res = audit_enqueue.enqueue(root, producer="saipal", body="# Test Audit\n\nBody", producer_operation_id="op-crash-safe")
        self.assertTrue(res["ok"])
        self.assertEqual(res["layer"], 1)
        self.assertTrue((audit_dir / "1.md").is_file())
        self.assertIn("Test Audit", (audit_dir / "1.md").read_text(encoding="utf-8"))

    def test_c21_duplicate_causal_findings_no_duplicate_repair_ticket(self):
        root = _make_project()
        adapter = saipal_adapter.SaipalAdapter()
        body1 = "# Audit Finding PAL-CAUSAL-1\nShared causal defect\n"
        digest1 = hashlib.sha256(body1.encode("utf-8")).hexdigest()
        finding1 = {
            "finding_id": "PAL-CAUSAL-1",
            "state": "QUALIFIED",
            "drift_class": "STATE_DRIFT",
            "severity": "P1",
            "root_cause": "Shared causal defect",
            "rule_ids": ["RULE-01"],
            "change_target": "ENGINE",
            "qualification_receipt": write_qualification_artifact(root, "QUAL-REC-PAL-CAUSAL-1"),
            "audit_body": body1,
            "artifact_digest": digest1,
        }
        res1 = adapter.deliver_finding_to_audit_inbox(root, finding1, publication_authorized=True)
        self.assertTrue(res1["ok"])

        finding2 = dict(finding1)
        res2 = adapter.deliver_finding_to_audit_inbox(root, finding2, publication_authorized=True)
        self.assertTrue(res2["ok"])
        self.assertTrue(res2["receipt"]["idempotent"])
        self.assertEqual(res1["receipt"]["layer"], res2["receipt"]["layer"])

    def test_c24_repair_verified_closure_linked_to_finding(self):
        root = _make_project()
        adapter = saipal_adapter.SaipalAdapter()
        (root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n## TODO\n## BLOCKED\n## DONE\n- [x] T-100 [P1] Task 100\n",
            encoding="utf-8",
        )
        verification_rel = write_verification_receipt(
            root, "t100-test-suite", {"suite": "test_suite", "result": "pass"}
        )
        res = adapter.record_maintainer_disposition(
            root,
            "PAL-CAUSAL-1",
            disposition="VERIFIED",
            task_id="T-100",
            closure_commit="commit-abcdef123456",
            verification_evidence=verification_rel,
        )
        self.assertTrue(res["ok"])
        history = adapter.get_dispositions(root)
        self.assertTrue(history["ok"], history)
        disps = history["records"]
        self.assertEqual(len(disps), 1)
        self.assertEqual(disps[0]["closure_commit"], "commit-abcdef123456")
        self.assertEqual(disps[0]["task_id"], "T-100")
        self.assertEqual(disps[0]["verification_evidence"], verification_rel)

    def test_c25_repair_fails_regression_remains_open(self):
        root = _make_project()
        adapter = saipal_adapter.SaipalAdapter()
        res = adapter.record_maintainer_disposition(
            root, "PAL-FAILED-1", disposition="REGRESSION_FAILED", task_id="T-100", notes="Failed unit test SuiteX"
        )
        self.assertTrue(res["ok"])
        history = adapter.get_dispositions(root)
        self.assertTrue(history["ok"], history)
        disps = history["records"]
        self.assertEqual(disps[-1]["disposition"], "REGRESSION_FAILED")

    def test_c26_recurrence_after_repair_links_evidence(self):
        root = _make_project()
        adapter = saipal_adapter.SaipalAdapter()
        adapter.record_maintainer_disposition(root, "PAL-REC-1", disposition="REPAIRED", task_id="T-90")
        res_rec = adapter.record_maintainer_disposition(
            root, "PAL-REC-1", disposition="RECURRED", task_id="T-100", notes="Recurred in session 987"
        )
        self.assertTrue(res_rec["ok"])
        history = adapter.get_dispositions(root)
        self.assertTrue(history["ok"], history)
        disps = [d for d in history["records"] if d["finding_id"] == "PAL-REC-1"]
        self.assertEqual(len(disps), 2)
        self.assertEqual(disps[0]["disposition"], "REPAIRED")
        self.assertEqual(disps[1]["disposition"], "RECURRED")

    def test_c28_provider_rate_limit_failure_classification(self):
        klass = supervisor.classify_failure(1, "429 Too Many Requests: Rate limit exceeded")
        self.assertEqual(klass, supervisor.RATE_LIMITED)
        self.assertEqual(supervisor.FAILURE_POLICY[klass], "BACKOFF_RETRY")

    def test_c29_capability_mismatch_failure_classification(self):
        klass = supervisor.classify_failure(1, "model does not support tools or tool use")
        self.assertEqual(klass, supervisor.CAPABILITY_UNAVAILABLE)
        self.assertEqual(supervisor.FAILURE_POLICY[klass], "FALLBACK_OR_OPERATOR")

    def test_c33_new_source_arrives_during_quiescence_wakes(self):
        root = _make_project()
        ctrl = campaign.CampaignController(root)
        ctrl.admit_campaign(
            campaign_id="CAMP-WAKE-TEST",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        state = campaign.load_campaign_state(root)
        state["campaign_state"] = campaign.QUIESCENT_WAIT
        state["wake_condition"] = {"event": "new_source_or_audit"}
        campaign.save_campaign_state(root, state)
        step_res = ctrl.step(worker_func=lambda r, g: {"progress_verified": True})
        self.assertTrue(step_res["ok"])
        self.assertIn(step_res["event"], ("WORKER_GENERATION_EXECUTED", "AUDIT_AVAILABLE"))
        st_after = campaign.load_campaign_state(root)
        self.assertEqual(st_after["campaign_state"], campaign.RUNNING)

    def test_c35_c36_all_work_complete_legitimately_quiescent(self):
        root = _make_project()
        (root / ".saipen" / "BOARD.md").write_text("## DOING\n## TODO\n## BLOCKED\n## DONE\n", encoding="utf-8")
        st_txt = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        st_txt = re.sub(r"(?m)^task:.*$", "task: none", st_txt)
        st_txt = re.sub(r"(?m)^phase:.*$", "phase: DONE", st_txt)
        (root / ".saipen" / "STATE.md").write_text(st_txt, encoding="utf-8")
        ctrl = campaign.CampaignController(root)
        ctrl.admit_campaign(
            campaign_id="CAMP-QUIESCENT-TEST",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        step_res = ctrl.step(worker_func=lambda r, g: {"progress_verified": True})
        self.assertTrue(step_res["ok"])
        st = campaign.load_campaign_state(root)
        self.assertIn(st["campaign_state"], (campaign.QUIESCENT_WAIT, campaign.OPERATOR_BLOCKED))

    def test_c38_cross_project_authority_missing(self):
        root = _make_project()
        payload = host_dispatch.build_dispatch_payload(root, campaign_id="CAMP-FOREIGN")
        payload["project_root"] = "V:/foreign_project_path"
        res = host_dispatch.dispatch_next_turn(root, payload, print_advisory=False)
        self.assertTrue(res["ok"])

    def test_c39_protocol_binding_unavailable_classifies_blocker(self):
        adapter = saipal_adapter.SaipalAdapter(saipal_home=Path("V:/missing_binding"))
        res = adapter.probe()
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], saipal_adapter.RUNTIME_UNAVAILABLE)

    def test_c40_native_runtime_parity_check(self):
        root = _make_project()
        lineage = host_dispatch.resolve_project_lineage(root)
        self.assertTrue(bool(lineage))
        self.assertTrue(lineage.startswith("lineage-") or lineage.startswith("git-"))

    def test_c23_maintainer_disposition_recorded(self):
        root = _make_project()
        adapter = saipal_adapter.SaipalAdapter()
        res = adapter.record_maintainer_disposition(
            root, "PAL-9999", disposition="REPAIRED", task_id="T-100", closure_commit="sha12345"
        )
        self.assertTrue(res["ok"])
        history = adapter.get_dispositions(root)
        self.assertTrue(history["ok"], history)
        disps = history["records"]
        self.assertEqual(len(disps), 1)
        self.assertEqual(disps[0]["finding_id"], "PAL-9999")
        self.assertEqual(disps[0]["disposition"], "REPAIRED")

    def test_c27_c34_no_hot_polling_eligibility(self):
        root = _make_project()
        adapter = saipal_adapter.SaipalAdapter()
        past_str = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(seconds=600)).strftime("%Y-%m-%dT%H:%M:%SZ")
        adapter.save_checkpoint(root, {"last_run_at": past_str})
        elig = adapter.get_next_eligibility(root, interval_seconds=300.0)
        self.assertTrue(elig["due"])

    def test_c30_campaign_controller_restarted_reconstructs_objective(self):
        root = _make_project()
        c1 = campaign.CampaignController(root)
        c1.admit_campaign(
            campaign_id="CAMP-DURABLE-123",
            horizon="OVERNIGHT",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        c2 = campaign.CampaignController(root)
        st = campaign.load_campaign_state(root)
        self.assertIsNotNone(st)
        self.assertEqual(st["campaign_id"], "CAMP-DURABLE-123")
        self.assertEqual(st["resource_budget"]["max_cycles"], 100)

    def test_c31_simultaneous_controllers_one_owner(self):
        root = _make_project()
        c1 = campaign.CampaignController(root)
        c1.admit_campaign(
            campaign_id="CAMP-LOCK-TEST",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        lock_file = root / campaign.LOCK_REL
        lk = lock.FileWriterLock(lock_file, root, blocking=False)
        lk.acquire()
        try:
            c2 = campaign.CampaignController(root)
            step_res = c2.step()
            self.assertFalse(step_res["ok"])
            self.assertEqual(step_res["code"], "CAMPAIGN_LOCKED")
        finally:
            lk.release()

    def test_c32_user_cancellation(self):
        root = _make_project()
        ctrl = campaign.CampaignController(root)
        ctrl.admit_campaign(
            campaign_id="CAMP-CANCEL-TEST",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        res_cancel = ctrl.cancel(reason="operator requested stop")
        self.assertTrue(res_cancel["ok"])
        self.assertEqual(res_cancel["status"], campaign.CANCELLED)
        step_res = ctrl.step(worker_func=lambda r, g: {"progress_verified": True})
        self.assertTrue(step_res["ok"])
        self.assertTrue(step_res["stopped"])
        self.assertEqual(step_res["status"], campaign.CANCELLED)

    def test_c37_host_lacks_native_post_turn_scheduling(self):
        root = _make_project()
        payload = host_dispatch.build_dispatch_payload(root, campaign_id="CAMP-ADVISORY-TEST")
        res = host_dispatch.dispatch_next_turn(root, payload, host_hook=None, print_advisory=False)
        self.assertTrue(res["ok"])
        self.assertFalse(res["dispatched"], "File advisory must not claim confirmed dispatch")
        self.assertEqual(res["status"], host_dispatch.HOST_DISPATCH_UNAVAILABLE)
        self.assertEqual(res["mode"], "file_advisory")
        self.assertTrue(Path(res["next_turn_path"]).is_file())

    # =========================================================================
    # NEGATIVE DEFECT CONTROLS (reproducing and guarding all 9 defects)
    # =========================================================================

    def test_neg01_admission_without_grant_witness_cannot_execute(self):
        """Negative control 1: Admission without grant witness creates PROPOSED state, step refuses execution."""
        root = _make_project(with_grant=False)
        ctrl = campaign.CampaignController(root)
        # Attempt admission with invented scope and no grant proof
        res = ctrl.admit_campaign(
            campaign_id="CAMP-UNVERIFIED",
            authority_scope="continuous_maintenance",
            authority_proof_reference="nonexistent/grant/path.json",
        )
        self.assertFalse(res["ok"], "Missing grant proof file must be refused")
        self.assertEqual(res["code"], "INVALID_AUTHORITY_GRANT")

        # Admission with no grant reference enters non-executable PROPOSED state
        res_prop = ctrl.admit_campaign(campaign_id="CAMP-PROP")
        self.assertTrue(res_prop["ok"])
        self.assertFalse(res_prop["admitted"], "Must not be executable")
        self.assertEqual(res_prop["status"], campaign.PROPOSED)

        # Stepping an unadmitted proposal fails closed
        step_res = ctrl.step(worker_func=lambda r, g: {"progress_verified": True})
        self.assertFalse(step_res["ok"])
        self.assertEqual(step_res["code"], "CAMPAIGN_NOT_ADMITTED")

    def test_neg02_unverified_finding_cannot_publish(self):
        """Negative control 2: PENDING/unconfirmed finding cannot publish even with P0/P1 severity."""
        root = _make_project()
        adapter = saipal_adapter.SaipalAdapter()
        finding = {
            "finding_id": "PAL-PENDING-1",
            "state": "PENDING",  # Not qualified!
            "severity": "P0",
            "drift_class": "CORRUPTION",
        }
        res = adapter.deliver_finding_to_audit_inbox(root, finding, publication_authorized=True)
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "NOT_QUALIFIED")

    def test_neg03_active_work_executes_worker_and_records_progress(self):
        """Negative control 3: Step on ACTIVE_WORK launches worker generation and checks progress evidence."""
        root = _make_project()
        ctrl = campaign.CampaignController(root)
        ctrl.admit_campaign(
            campaign_id="CAMP-EXEC-TEST",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        called = []

        def mock_worker(project_root, generation):
            called.append(generation)
            return {"progress_verified": True, "mutated": True}

        res = ctrl.step(worker_func=mock_worker)
        self.assertTrue(res["ok"])
        self.assertEqual(res["event"], "WORKER_GENERATION_EXECUTED")
        self.assertEqual(called, [1])
        self.assertTrue(res["progress"]["made_progress"])

    def test_neg04_source_available_handled_explicitly(self):
        """Negative control 4: SOURCE_AVAILABLE is handled cleanly, never UNHANDLED_CLASSIFICATION."""
        root = _make_project()
        ctrl = campaign.CampaignController(root)
        ctrl.admit_campaign(
            campaign_id="CAMP-SOURCE-TEST",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        with mock.patch("saipen_engine.continuation_assessment.assess_continuation") as mock_assess:
            mock_assess.return_value = {
                "classification": ca.SOURCE_AVAILABLE,
                "action": "saipen source project",
            }
            res = ctrl.step()
            self.assertTrue(res["ok"])
            self.assertEqual(res["event"], "SOURCE_AVAILABLE")

    def test_neg05_invalid_runtime_returns_explicit_failure(self):
        """Negative control 5: INVALID_RUNTIME returns ok=False, never ok=true UNHANDLED_CLASSIFICATION."""
        root = _make_project()
        ctrl = campaign.CampaignController(root)
        ctrl.admit_campaign(
            campaign_id="CAMP-INV-TEST",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        with mock.patch("saipen_engine.continuation_assessment.assess_continuation") as mock_assess:
            mock_assess.return_value = {
                "classification": ca.INVALID_RUNTIME,
                "detail": "corrupted state header",
            }
            res = ctrl.step()
            self.assertFalse(res["ok"])
            self.assertEqual(res["code"], "INVALID_RUNTIME")

    def test_neg06_two_parallel_host_dispatches_execute_callback_once(self):
        """Negative control 6: Concurrent dispatch requests execute host hook exactly once."""
        root = _make_project()
        callback_hits = []

        def flaky_hook(p):
            callback_hits.append(p)
            time.sleep(0.01)
            return {
                "schema_version": 1,
                "status": host_dispatch.HOST_ACCEPTED,
                "campaign_id": p["campaign_id"],
                "iteration_id": p["iteration_id"],
                "worker_generation": p["worker_generation"],
                "idempotency_key": p["idempotency_key"],
                "project_lineage": p["project_lineage"],
                "accepted_request_id": p["idempotency_key"],
                "accepting_host": "native_test_host",
            }

        payload = host_dispatch.build_dispatch_payload(
            root, campaign_id="CAMP-RACE", worker_generation=1, iteration_id=1
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(host_dispatch.dispatch_next_turn, root, payload, host_hook=flaky_hook, print_advisory=False),
                pool.submit(host_dispatch.dispatch_next_turn, root, payload, host_hook=flaky_hook, print_advisory=False),
            ]
            results = [f.result() for f in futures]

        self.assertEqual(len(callback_hits), 1)

    def test_neg07_rejected_host_hook_reported_as_dispatch_refused(self):
        """Negative control 7: Structured rejection from host_hook is DISPATCH_REFUSED, not success."""
        root = _make_project()
        payload = host_dispatch.build_dispatch_payload(root, campaign_id="CAMP-REJECT-TEST")
        refusing_hook = lambda p: {"ok": False, "error": "Capacity exceeded"}
        res = host_dispatch.dispatch_next_turn(root, payload, host_hook=refusing_hook, print_advisory=False)
        self.assertFalse(res["ok"])
        self.assertFalse(res["dispatched"])
        self.assertEqual(res["status"], host_dispatch.DISPATCH_REFUSED)

    def test_neg08_failed_dispatch_is_retryable_on_same_controller(self):
        """Negative control 8: A failed dispatch does not block a subsequent retry."""
        root = _make_project()
        ctrl = host_iteration.HostIterationController(
            required={"filesystem", "git"},
            project_root=root,
        )
        verdict = {
            "decision": iteration.AUTO_KICK,
            "canonical_task": "T-100",
            "phase": "BUILD",
        }
        # First attempt: hook fails
        failing_hook = lambda p: {"ok": False, "error": "Transient failure"}
        turn_ctx1 = {"project_root": root, "iteration_id": 1, "host_hook": failing_hook}
        ctrl.on_model_turn_finished(verdict, turn_context=turn_ctx1)
        # Idempotency key must NOT be locked in _dispatched_idempotency_keys
        payload = host_dispatch.build_dispatch_payload(root, iteration_id=1)
        self.assertNotIn(payload["idempotency_key"], ctrl._dispatched_idempotency_keys)

        # Second attempt: hook succeeds
        succeeding_hook = lambda p: {
            "schema_version": 1,
            "status": host_dispatch.HOST_ACCEPTED,
            "campaign_id": p["campaign_id"],
            "iteration_id": p["iteration_id"],
            "worker_generation": p["worker_generation"],
            "idempotency_key": p["idempotency_key"],
            "project_lineage": p["project_lineage"],
            "accepted_request_id": p["idempotency_key"],
            "accepting_host": "native_test_host",
        }
        turn_ctx2 = {"project_root": root, "iteration_id": 1, "host_hook": succeeding_hook}
        ctrl.on_model_turn_finished(verdict, turn_context=turn_ctx2)
        self.assertIn(payload["idempotency_key"], ctrl._dispatched_idempotency_keys)

    def test_neg09_corrupted_campaign_state_overwritten_rejected(self):
        """Negative control 9: Corrupted state.json is NOT silently overwritten by admission."""
        root = _make_project()
        state_file = campaign.campaign_state_path(root)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("{not: valid: json", encoding="utf-8")

        ctrl = campaign.CampaignController(root)
        res = ctrl.admit_campaign(
            campaign_id="CAMP-NEW",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        self.assertFalse(res["ok"])
        self.assertEqual(res["code"], "STATE_CORRUPT")
        # Ensure file was not overwritten
        self.assertEqual(state_file.read_text(encoding="utf-8"), "{not: valid: json")


if __name__ == "__main__":
    unittest.main()
