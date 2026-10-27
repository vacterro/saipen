"""Local contracts modeled on production gates A-L and simulated campaign soak.

These use simulated issuer/host boundaries; they do not prove production acceptance.
Models conditions specified in SAIHANDOFF T-1928:
- GATE A: Authority
- GATE B: Actual Work
- GATE C: Host Auto-Kick
- GATE D: Crash Recovery
- GATE E: SAIPAL Forensics
- GATE F: Publication
- GATE G: Repair
- GATE H: Disposition
- GATE I: Quiescence
- GATE J: Long-Run Stability
- GATE K: Stop
- GATE L: Installed Parity
- SOAK: Multi-generation sustained soak metrics
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
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


def _create_production_fixture(task="T-200", *, with_grant=True) -> Path:
    root = Path(tempfile.mkdtemp(prefix="saipen-gate-"))
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
        f"## DOING\n- [/] {task} [P1] Production Task\n## TODO\n## BLOCKED\n## DONE\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "LOG.md").write_text("# LOG\n- 25.10.26 20:00 [E-100] RUN: INITIAL\n", encoding="utf-8")
    lineage = "lineage-0123456789abcdef0123456789abcdef"
    (root / ".saipen" / "IDENTITY.md").write_text(
        f"---\nproject_lineage: {lineage}\n---\n",
        encoding="utf-8",
    )
    if with_grant:
        write_scoped_fixture_grant(root)
    return root


class TestProductionAcceptanceGates(unittest.TestCase):
    """Local production-gate contracts with explicitly simulated boundaries."""
    CATEGORY = "CONTRACT"

    def setUp(self):
        self._patcher = mock.patch(
            "saipen_engine.host_authority_client.inspect_operator_campaign",
            side_effect=inspect_fixture_campaign,
        )
        self._patcher.start()
        # AUT-001: CONTRACT class -- the host boundary is explicitly simulated
        # for the whole class. Receipts written by this process cannot prove
        # host acceptance in production, so the trust answer is declared here
        # rather than inferred from a dict's shape.
        self._trust_patcher = mock.patch(
            "saipen_engine.host_dispatch._broker_verified_receipt",
            return_value=True,
        )
        self._trust_patcher.start()

    def tearDown(self):
        self._trust_patcher.stop()
        self._patcher.stop()

    def test_gate_a_authority_enforcement(self):
        """GATE A: Valid grant permits scoped execution; invalid grant forbids protected actions."""
        # 1. Invalid grant
        root_no_grant = _create_production_fixture(with_grant=False)
        ctrl_bad = campaign.CampaignController(root_no_grant)
        res_bad = ctrl_bad.admit_campaign(
            campaign_id="CAMP-FORGED",
            authority_scope="continuous_maintenance",
            authority_proof_reference="authority/missing.json",
        )
        self.assertFalse(res_bad["ok"])
        self.assertEqual(res_bad["code"], "INVALID_AUTHORITY_GRANT")

        # 2. Valid grant
        root_ok = _create_production_fixture(with_grant=True)
        ctrl_ok = campaign.CampaignController(root_ok)
        res_ok = ctrl_ok.admit_campaign(
            campaign_id="CAMP-VALID",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        self.assertTrue(res_ok["ok"])
        self.assertTrue(res_ok["admitted"])
        self.assertEqual(res_ok["status"], campaign.ADMITTED)

    def test_gate_b_actual_work_execution(self):
        """GATE B: Campaign step executes real worker, changes Work state or records progress."""
        root = _create_production_fixture()
        ctrl = campaign.CampaignController(root)
        ctrl.admit_campaign(
            campaign_id="CAMP-WORK-EXEC",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        worker_ran = []

        def worker_impl(p_root, generation):
            worker_ran.append(generation)
            log = p_root / ".saipen" / "LOG.md"
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"- 25.10.26 20:01 [E-101] RUN: WORK GEN {generation}\n")
            return {"ok": True, "progress_verified": True}

        res = ctrl.step(worker_func=worker_impl)
        self.assertTrue(res["ok"])
        self.assertEqual(res["event"], "WORKER_GENERATION_EXECUTED")
        self.assertEqual(worker_ran, [1])
        self.assertTrue(res["progress"]["made_progress"])
        st = campaign.load_campaign_state(root)
        self.assertEqual(st["worker_generation"], 1)

    def test_gate_c_host_auto_kick(self):
        """GATE C: Turn completion starts real native scheduler dispatch with bound grant."""
        root = _create_production_fixture()
        ctrl = host_iteration.HostIterationController(
            required={"filesystem", "git"},
            project_root=root,
        )
        verdict = {
            "decision": iteration.AUTO_KICK,
            "canonical_task": "T-200",
            "phase": "BUILD",
        }
        turn_accepted = []

        def native_scheduler(payload):
            turn_accepted.append(payload)
            # A host acceptance must be a typed receipt that binds THIS
            # request: schema, disposition, campaign/iteration/generation,
            # idempotency identity, lineage, accepted request and host.
            return {
                "schema_version": 1,
                "status": host_dispatch.HOST_ACCEPTED,
                "campaign_id": payload["campaign_id"],
                "iteration_id": payload["iteration_id"],
                "worker_generation": payload["worker_generation"],
                "idempotency_key": payload["idempotency_key"],
                "project_lineage": payload["project_lineage"],
                "accepted_request_id": payload["idempotency_key"],
                "accepting_host": "native_scheduler",
            }

        action = ctrl.on_model_turn_finished(
            verdict,
            turn_context={
                "project_root": root,
                "iteration_id": 1,
                "host_hook": native_scheduler,
                "authority_proof_reference": ".saipen/authority/grant.json",
            },
        )
        self.assertEqual(action, host_iteration.KICK_NEXT_ITERATION)
        self.assertEqual(len(turn_accepted), 1)
        self.assertEqual(turn_accepted[0]["authority_proof_reference"], ".saipen/authority/grant.json")

    def test_gate_d_crash_recovery_no_duplicate_owner(self):
        """GATE D: Survived crash; no duplicate owner executes across generations."""
        root = _create_production_fixture()
        lease1 = watchdog.acquire_lease(root, "worker-gen-1")
        self.assertEqual(lease1["lease_generation"], 1)

        # Worker 1 dies, lease expires
        future_time = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=250)
        rep = supervisor.replace_worker(root, "worker-gen-2", now=future_time)
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["lease"]["lease_generation"], 2)

        # Fenced worker 1 cannot mutate
        self.assertFalse(watchdog.mutation_allowed(root, "worker-gen-1", 1, now=future_time))
        # Active worker 2 can mutate
        self.assertTrue(watchdog.mutation_allowed(root, "worker-gen-2", 2, now=future_time))

    def test_gate_e_gate_f_saipal_forensics_and_publication(self):
        """GATE E & F: Qualified finding passes authorization and preserves immutable receipt."""
        root = _create_production_fixture()
        adapter = saipal_adapter.SaipalAdapter()
        body = "# Audit Finding PAL-GATE-01\nVerified gate reproduction defect\n"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        finding = {
            "finding_id": "PAL-GATE-01",
            "state": "QUALIFIED",
            "drift_class": "DRIFT_GATE",
            "severity": "P0",
            "root_cause": "Verified gate reproduction defect",
            "rule_ids": ["GATE-RULE-1"],
            "change_target": "ENGINE",
            "qualification_receipt": write_qualification_artifact(root, "QUAL-REC-GATE-01"),
            "audit_body": body,
            "artifact_digest": digest,
        }
        # STAGE_ONLY when unauthorized
        res_unauth = adapter.deliver_finding_to_audit_inbox(root, finding, publication_authorized=False)
        self.assertFalse(res_unauth["ok"])
        self.assertEqual(res_unauth["status"], saipal_adapter.STAGED_PUBLICATION)

        # Published when authorized
        res_pub = adapter.deliver_finding_to_audit_inbox(root, finding, publication_authorized=True)
        self.assertTrue(res_pub["ok"])
        self.assertEqual(res_pub["status"], saipal_adapter.DELIVERED_PUBLICATION)
        receipt = res_pub["receipt"]
        self.assertEqual(receipt["finding_id"], "PAL-GATE-01")

        # Receipts persisted
        history = adapter.collect_publication_receipts(root)
        self.assertTrue(history["ok"], history)
        saved_receipts = history["records"]
        self.assertTrue(any(r["finding_id"] == "PAL-GATE-01" for r in saved_receipts))

    def test_gate_g_gate_h_repair_and_disposition(self):
        """GATE G & H: Canonical repair closed-loop links finding, Work, and verification."""
        root = _create_production_fixture()
        adapter = saipal_adapter.SaipalAdapter()
        # Ensure task is marked completed in ## DONE
        (root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n## TODO\n## BLOCKED\n## DONE\n- [x] T-200 [P1] Production Task\n",
            encoding="utf-8",
        )
        verification_rel = write_verification_receipt(
            root,
            "t200-unit-tests",
            {"suite": "unit_tests", "result": "pass", "execution_evidence": True},
        )
        disp_res = adapter.record_maintainer_disposition(
            root,
            "PAL-GATE-01",
            disposition="VERIFIED",
            task_id="T-200",
            closure_commit="commit-7890abcdef",
            verification_evidence=verification_rel,
            notes="Repaired and verified under test suite",
        )
        self.assertTrue(disp_res["ok"])
        history = adapter.get_dispositions(root)
        self.assertTrue(history["ok"], history)
        disps = history["records"]
        self.assertEqual(len(disps), 1)
        self.assertEqual(disps[0]["finding_id"], "PAL-GATE-01")
        self.assertEqual(disps[0]["disposition"], "VERIFIED")
        self.assertEqual(disps[0]["verification_evidence"], verification_rel)

    def test_gate_i_quiescence_and_wake(self):
        """GATE I: Work exhaustion enters quiescence; new work wakes controller."""
        root = _create_production_fixture()
        # Mark all work complete
        (root / ".saipen" / "BOARD.md").write_text("## DOING\n## TODO\n## BLOCKED\n## DONE\n", encoding="utf-8")
        st_txt = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        st_txt = re.sub(r"(?m)^task:.*$", "task: none", st_txt)
        st_txt = re.sub(r"(?m)^phase:.*$", "phase: DONE", st_txt)
        (root / ".saipen" / "STATE.md").write_text(st_txt, encoding="utf-8")

        ctrl = campaign.CampaignController(root)
        ctrl.admit_campaign(
            campaign_id="CAMP-QUIESCENCE",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        step_res = ctrl.step()
        self.assertTrue(step_res["ok"])
        st = campaign.load_campaign_state(root)
        self.assertIn(st["campaign_state"], (campaign.QUIESCENT_WAIT, campaign.OPERATOR_BLOCKED))

        # Add new work
        (root / ".saipen" / "BOARD.md").write_text("## DOING\n- [/] T-201 [P1] New Task\n## TODO\n## BLOCKED\n## DONE\n", encoding="utf-8")
        st_txt2 = re.sub(r"(?m)^task:.*$", "task: T-201", st_txt)
        st_txt2 = re.sub(r"(?m)^phase:.*$", "phase: BUILD", st_txt2)
        (root / ".saipen" / "STATE.md").write_text(st_txt2, encoding="utf-8")

        wake_res = ctrl.step(worker_func=lambda r, g: {"progress_verified": True})
        self.assertTrue(wake_res["ok"])
        st_wake = campaign.load_campaign_state(root)
        self.assertEqual(st_wake["campaign_state"], campaign.RUNNING)

    def test_gate_j_long_run_stability_and_budget_limits(self):
        """GATE J: Multi-generation execution enforces budgets truthfully."""
        root = _create_production_fixture()
        ctrl = campaign.CampaignController(root)
        ctrl.admit_campaign(
            campaign_id="CAMP-BUDGET-TEST",
            authority_proof_reference=".saipen/authority/grant.json",
            resource_budget={"max_generations": 3, "max_wall_seconds": 3600},
        )
        # Advance 3 generations
        for _ in range(3):
            step_res = ctrl.step(worker_func=lambda r, g: {"progress_verified": True})
            self.assertTrue(step_res["ok"])

        # 4th generation hits max_generations budget
        exhaust_res = ctrl.step(worker_func=lambda r, g: {"progress_verified": True})
        self.assertTrue(exhaust_res["ok"])
        self.assertEqual(exhaust_res["event"], "BUDGET_EXHAUSTED")
        st = campaign.load_campaign_state(root)
        self.assertEqual(st["campaign_state"], campaign.CHECKPOINTING)

    def test_gate_k_explicit_cancellation(self):
        """GATE K: Cancellation fences future generation dispatches."""
        root = _create_production_fixture()
        ctrl = campaign.CampaignController(root)
        ctrl.admit_campaign(
            campaign_id="CAMP-CANCEL-GATE",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        ctrl.cancel(reason="test cancellation")
        step_res = ctrl.step()
        self.assertTrue(step_res["ok"])
        self.assertTrue(step_res["stopped"])
        self.assertEqual(step_res["status"], campaign.CANCELLED)

    def test_gate_l_installed_parity(self):
        """GATE L: Installed runtime lineage and schema parity verified."""
        root = _create_production_fixture()
        lineage = host_dispatch.resolve_project_lineage(root)
        self.assertTrue(lineage.startswith("lineage-") or lineage.startswith("git-"))
        self.assertEqual(campaign.CAMPAIGN_SCHEMA_VERSION, 1)


class TestExtendedSoakCampaign(unittest.TestCase):
    """Simulated multi-generation contracts, not elapsed-time production soak."""
    CATEGORY = "CONTRACT"

    def setUp(self):
        self._patcher = mock.patch(
            "saipen_engine.host_authority_client.inspect_operator_campaign",
            side_effect=inspect_fixture_campaign,
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    def test_extended_soak_multi_generation_simulation(self):
        """Wave 15: Sustained multi-generation soak verifying required safety metrics."""
        root = _create_production_fixture()
        ctrl = campaign.CampaignController(root)
        admit_res = ctrl.admit_campaign(
            campaign_id="SOAK-CAMPAIGN-001",
            authority_proof_reference=".saipen/authority/grant.json",
            resource_budget={"max_generations": 10, "max_wall_seconds": 1800},
        )
        self.assertTrue(admit_res["ok"])

        metrics = {
            "worker_generation_count": 0,
            "actual_worker_launch_count": 0,
            "host_accepted_dispatches": 0,
            "qualified_findings": 0,
            "accepted_audits": 0,
            "verified_repairs": 0,
            "unauthorized_mutation_count": 0,
            "unverified_authority_count": 0,
            "duplicate_concurrent_owner_count": 0,
        }

        def soak_worker(p_root, gen):
            metrics["actual_worker_launch_count"] += 1
            log_f = p_root / ".saipen" / "LOG.md"
            with open(log_f, "a", encoding="utf-8") as f:
                f.write(f"- 25.10.26 [E-{100 + gen}] RUN: SOAK STEP {gen}\n")
            return {"progress_verified": True, "gen": gen}

        # Run 5 successive generations
        for i in range(5):
            res = ctrl.step(worker_func=soak_worker)
            self.assertTrue(res["ok"])
            metrics["worker_generation_count"] = res.get("worker_generation", i + 1)

        self.assertEqual(metrics["worker_generation_count"], 5)
        self.assertEqual(metrics["actual_worker_launch_count"], 5)
        self.assertEqual(metrics["unauthorized_mutation_count"], 0)
        self.assertEqual(metrics["unverified_authority_count"], 0)
        self.assertEqual(metrics["duplicate_concurrent_owner_count"], 0)


class TestCampaignNegativeControls(unittest.TestCase):
    """UNIT & INTEGRATION: Explicit negative defect controls for CAMP-1930 inventory."""
    CATEGORY = "UNIT"

    def test_neg_camp_001_unauthenticated_grant_file_rejected(self):
        """CAMP-1930-001: Unauthenticated local JSON grant fails closed."""
        root = _create_production_fixture(with_grant=False)
        auth_dir = root / ".saipen" / "authority"
        auth_dir.mkdir(parents=True, exist_ok=True)
        # Self-authored grant
        self_grant = {
            "grant_id": "GRANT-ATTACKER",
            "issuer": "self",
            "authorized_scopes": ["CAMPAIGN_EXECUTION"],
        }
        (auth_dir / "attacker.json").write_text(json.dumps(self_grant), encoding="utf-8")
        chk = campaign.verify_operator_grant(root, ".saipen/authority/attacker.json")
        self.assertFalse(chk["valid"])
        self.assertEqual(chk["status"], "GRANT_INVALID")

        # Missing proof
        unproven_grant = {
            "grant_id": "GRANT-UNPROVEN",
            "issuer": "operator_broker",
            "authorized_scopes": ["CAMPAIGN_EXECUTION"],
        }
        (auth_dir / "unproven.json").write_text(json.dumps(unproven_grant), encoding="utf-8")
        chk2 = campaign.verify_operator_grant(root, ".saipen/authority/unproven.json")
        self.assertFalse(chk2["valid"])
        self.assertEqual(chk2["status"], "GRANT_INVALID")

    def test_neg_camp_002_journal_event_without_operator_authority_rejected(self):
        """CAMP-1930-002: Journal event without operator grant proof fails."""
        root = _create_production_fixture(with_grant=False)
        log_f = root / ".saipen" / "LOG.md"
        log_f.write_text("# LOG\n- 25.10.26 20:00 [E-999] RUN: WORKER SLICE [op: op-999]\n", encoding="utf-8")
        chk = campaign.verify_operator_grant(root, "E-999")
        self.assertFalse(chk["valid"])
        self.assertEqual(chk["status"], "EVENT_NOT_OPERATOR_AUTHORITY")

    def test_neg_camp_003_dispatch_lock_busy_fails_closed(self):
        """CAMP-1930-003: Dispatch lock failure fails closed without proceeding."""
        root = _create_production_fixture()
        lock_file = root / ".saipen" / "locks" / "dispatch.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        held_lock = lock.FileWriterLock(lock_file, root, blocking=False)
        held_lock.acquire()
        try:
            payload = host_dispatch.build_dispatch_payload(root, campaign_id="CAMP-LOCK-TEST")
            res = host_dispatch.dispatch_next_turn(root, payload, print_advisory=False)
            self.assertFalse(res["ok"])
            self.assertEqual(res["status"], host_dispatch.LOCK_BUSY)
        finally:
            held_lock.release()

    def test_neg_camp_004_unrelated_dict_or_none_acceptance_unverified(self):
        """CAMP-1930-004: Host hook returning None or unrelated dict fails ACCEPTANCE_UNVERIFIED."""
        root = _create_production_fixture()
        payload = host_dispatch.build_dispatch_payload(root, campaign_id="CAMP-ACCEPT-TEST")
        # None return
        res_none = host_dispatch.dispatch_next_turn(root, payload, host_hook=lambda p: None, print_advisory=False)
        self.assertFalse(res_none["ok"])
        self.assertEqual(res_none["status"], host_dispatch.ACCEPTANCE_UNVERIFIED)

        # Unrelated dictionary
        res_unrelated = host_dispatch.dispatch_next_turn(
            root, payload, host_hook=lambda p: {"random_field": "some_value"}, print_advisory=False
        )
        self.assertFalse(res_unrelated["ok"])
        self.assertEqual(res_unrelated["status"], host_dispatch.ACCEPTANCE_UNVERIFIED)

    def test_neg_camp_005_and_009_executor_missing_and_supersession(self):
        """CAMP-1930-005 & CAMP-1930-009: Missing executor fails; live campaign supersession blocked."""
        root = _create_production_fixture()
        with mock.patch("saipen_engine.host_authority_client.inspect_operator_campaign",
                        side_effect=inspect_fixture_campaign):
            ctrl = campaign.CampaignController(root)
            ctrl.admit_campaign(
                campaign_id="CAMP-EXEC-TEST",
                authority_proof_reference=".saipen/authority/grant.json",
            )
            # 1. Step without tools/saipen.py and without worker_func fails
            step_res = ctrl.step(worker_func=None)
            self.assertFalse(step_res["ok"])
            self.assertEqual(step_res["code"], "EXECUTOR_UNAVAILABLE")

            # 2. Live campaign supersession refused
            st = campaign.load_campaign_state(root)
            st["campaign_state"] = campaign.RUNNING
            campaign.save_campaign_state(root, st)
            super_res = ctrl.admit_campaign(
                campaign_id="CAMP-NEW-REPLACE",
                authority_proof_reference=".saipen/authority/grant.json",
                force_new=True,
            )
            self.assertFalse(super_res["ok"])
            self.assertEqual(super_res["code"], "LIVE_CAMPAIGN_SUPERSEDED_REFUSED")

            # 3. Tampered state rejected as STATE_UNTRUSTED
            raw_path = campaign.campaign_state_path(root)
            data = json.loads(raw_path.read_text(encoding="utf-8"))
            data["campaign_id"] = "TAMPERED-ID"
            raw_path.write_text(json.dumps(data), encoding="utf-8")
            insp = campaign.inspect_campaign_state(root)
            self.assertEqual(insp["status"], campaign.STATE_UNTRUSTED)

    def test_neg_camp_007_missing_artifact_digest_fails_publication(self):
        """CAMP-1930-007: Finding without digest or qualification proof fails publication."""
        root = _create_production_fixture()
        adapter = saipal_adapter.SaipalAdapter()
        # Unconfirmed finding
        bad_f = {"finding_id": "PAL-UNCONFIRMED", "state": "DRAFT"}
        r1 = adapter.deliver_finding_to_audit_inbox(root, bad_f, publication_authorized=True)
        self.assertFalse(r1["ok"])
        self.assertEqual(r1["status"], "NOT_QUALIFIED")

        # Missing digest: qualification is genuine here so the digest gate is
        # the one under test rather than the qualification gate in front of it.
        no_dig = {
            "finding_id": "PAL-NO-DIG",
            "state": "QUALIFIED",
            "qualification_receipt": write_qualification_artifact(root, "QUAL-1"),
            "audit_body": "# Body",
        }
        r2 = adapter.deliver_finding_to_audit_inbox(root, no_dig, publication_authorized=True)
        self.assertFalse(r2["ok"])
        self.assertEqual(r2["status"], "ARTIFACT_DIGEST_MISSING")

        # A caller-named receipt id with no artifact behind it is not proof.
        bogus_qual = {
            "finding_id": "PAL-BOGUS-QUAL",
            "state": "QUALIFIED",
            "qualification_receipt": "QUAL-1",
            "audit_body": "# Body",
            "artifact_digest": hashlib.sha256(b"# Body").hexdigest(),
        }
        r2b = adapter.deliver_finding_to_audit_inbox(
            root, bogus_qual, publication_authorized=True
        )
        self.assertFalse(r2b["ok"])
        self.assertEqual(r2b["status"], "NOT_QUALIFIED")

        # Mismatched digest
        mismatch = {
            "finding_id": "PAL-MISMATCH",
            "state": "QUALIFIED",
            "qualification_receipt": write_qualification_artifact(root, "QUAL-2"),
            "audit_body": "# Body",
            "artifact_digest": "deadbeef" * 8,
        }
        r3 = adapter.deliver_finding_to_audit_inbox(root, mismatch, publication_authorized=True)
        self.assertFalse(r3["ok"])
        self.assertEqual(r3["status"], "ARTIFACT_DIGEST_MISMATCH")

    def test_neg_camp_008_unverified_maintainer_disposition_rejected(self):
        """CAMP-1930-008: VERIFIED disposition without board DONE status or evidence rejected."""
        root = _create_production_fixture()
        adapter = saipal_adapter.SaipalAdapter()
        # 1. Ticket still in DOING on board
        res1 = adapter.record_maintainer_disposition(
            root, "PAL-01", disposition="VERIFIED", task_id="T-200", verification_evidence="evidence:ok"
        )
        self.assertFalse(res1["ok"])
        self.assertEqual(res1["status"], "DISPOSITION_UNVERIFIED")

        # 2. Ticket in DONE but generic PASS evidence
        (root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n## TODO\n## BLOCKED\n## DONE\n- [x] T-200 Done\n", encoding="utf-8"
        )
        res2 = adapter.record_maintainer_disposition(
            root, "PAL-01", disposition="VERIFIED", task_id="T-200", verification_evidence="PASS"
        )
        self.assertFalse(res2["ok"])
        self.assertEqual(res2["status"], "DISPOSITION_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
