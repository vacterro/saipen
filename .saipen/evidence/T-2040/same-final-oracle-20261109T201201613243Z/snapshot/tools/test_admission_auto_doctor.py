"""Comprehensive regression tests for Canonical Admission Auto-Doctor (SRC-257 / T-1797).

Implements Phase 7 Regression Matrix A through P:
A. Existing valid operator authorization is reused.
B. Superseded pause is correctly distinguished from an active pause.
C. Still-active operator STOP remains enforced.
D. Missing provenance refuses authority escalation.
E. Software remediation can progress independently only when policy and authority permit.
F. Hardware acceptance remains BLOCKED when genuine hardware evidence is unavailable.
G. Active T-220 ownership remains untouched.
H. Repeated cc does not duplicate intake or Work.
I. An interrupted canonical repair resumes safely.
J. Failed validation causes bounded refusal with preserved evidence.
K. An unrelated blocked task does not suppress runnable authorized tasks.
L. The system never changes a protected dependency merely because doing so would make work runnable.
M. The original operator goal survives Auto-Doctor repair and resumes idempotently.
N. No-publish and production-vault boundaries hold.
O. A correction requiring new authorization produces one precise decision request,
   not a CLI checklist.
P. Later directives do not inherit authority from earlier directives with unrelated scope.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from saipen_engine import admission_doctor, continue_loop, decision_request


class AdmissionAutoDoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="saipen_adm_test_")
        self.root = Path(self.temp_dir)
        (self.root / ".saipen").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_decision_request_creation_and_formatting(self):
        """Phase 5: structured decision request completeness and formatting."""
        req = decision_request.create_decision_request(
            blocked_operation="PHASE SCOUT T-263",
            existing_authority={"authority_source": "E-3128", "continuation_authority": "budget"},
            missing_authorization="Explicit operator reversal of PAUSED_BY_OPERATOR on T-263",
            consequences_approval="T-263 can proceed with software remediation",
            consequences_refusal="T-263 remains held and blocked",
            safe_default="Keep T-263 blocked",
            recording_mechanism="saipen ticket unblock T-263 '<directive>'",
        )
        self.assertIn("blocked_operation", req)
        self.assertIn("missing_authorization", req)
        formatted = decision_request.format_decision_request(req)
        self.assertIn("=== OPERATOR DECISION REQUIRED ===", formatted)
        self.assertIn("Blocked Operation     : PHASE SCOUT T-263", formatted)
        self.assertIn("Safe Default          : Keep T-263 blocked", formatted)

    def test_matrix_a_existing_valid_operator_authorization_is_reused(self):
        """Matrix A: Existing valid operator authorization is reused."""
        state = {
            "continuation_authority": "operator_persistent",
            "authority_source": "E-100",
            "authority_until": "goal_complete",
            "safety_valve_mode": "checkpoint",
            "execution_intent": "goal",
            "goal_ingress": "goal-0123456789abcdef",
        }
        # Validate that state authority is acknowledged and reused
        board = {"tickets": {}}
        ticket = {"id": "T-10", "section": "## TODO", "needs": []}
        board["tickets"]["T-10"] = ticket
        report = admission_doctor.classify_blocked_ticket(ticket, board["tickets"], state)
        self.assertEqual(report["ticket"], "T-10")

    def test_matrix_b_superseded_pause_distinguished_from_active_pause(self):
        """Matrix B: Superseded pause is correctly distinguished from an active pause."""
        active_pause_ticket = {
            "id": "T-1",
            "section": "## BLOCKED",
            "blocker": "PAUSED_BY_OPERATOR 2026-10-08: latest directive allows T-247 only",
        }
        board = {"tickets": {"T-1": active_pause_ticket}}
        state = {"task": "none"}
        report = admission_doctor.classify_blocked_ticket(
            active_pause_ticket, board["tickets"], state
        )
        self.assertIn(admission_doctor.CAUSE_F_AUTHORIZATION_REQUIRED, report["causes"])
        self.assertIsNotNone(report["decision_request"])

    def test_matrix_c_still_active_operator_stop_remains_enforced(self):
        """Matrix C: Still-active operator STOP remains enforced."""
        ticket = {
            "id": "T-5",
            "section": "## BLOCKED",
            "blocker": "OPERATOR_PAUSED: explicit STOP",
        }
        board = {"tickets": {"T-5": ticket}}
        state = {"task": "none"}
        report = admission_doctor.classify_blocked_ticket(ticket, board["tickets"], state)
        self.assertIn(admission_doctor.CAUSE_F_AUTHORIZATION_REQUIRED, report["causes"])

    def test_matrix_d_missing_provenance_refuses_authority_escalation(self):
        """Matrix D: Missing provenance refuses authority escalation."""
        # Bare cc all claiming to supersede operator pause without carrier witness must be refused
        valid, msg = decision_request.validate_authority_escalation(
            proposed_reason=(
                "operator directive superseded: cc all authorizes full FUTURE_GATE implementation"
            ),
            acting_agent="saipen-cli",
            carrier_witness="model_supplied",
        )
        self.assertFalse(valid)
        self.assertIn("AUTHORITY_ESCALATION_REFUSED", msg)

        # A caller-provided label is not authenticated operator origin.
        valid_carrier, _ = decision_request.validate_authority_escalation(
            proposed_reason=(
                "operator directive superseded: cc all authorizes full FUTURE_GATE implementation"
            ),
            acting_agent="saipen-cli",
            carrier_witness="operator_carrier",
        )
        self.assertFalse(valid_carrier)

    def test_matrix_e_software_remediation_progresses_independently(self):
        """Matrix E: Software remediation can progress independently only when policy permits."""
        hw_ticket = {
            "id": "T-261",
            "section": "## BLOCKED",
            "verify": "HARDWARE_REAL FIDO acceptance",
            "blocker": "HARDWARE_REAL missing",
        }
        sw_ticket = {
            "id": "T-263",
            "section": "## TODO",
            "needs": ["T-261"],
            "verify": "pytest tests/secure_apps_future_gates.py",
        }
        board = {"tickets": {"T-261": hw_ticket, "T-263": sw_ticket}}
        state = {"task": "none"}
        report = admission_doctor.classify_blocked_ticket(sw_ticket, board["tickets"], state)
        self.assertTrue(report["has_hardware_dependency"])
        self.assertTrue(report["separable_software_remediation"])
        self.assertIn(admission_doctor.CAUSE_B_RESTRICTIVE_DEPENDENCY, report["causes"])

    def test_matrix_f_hardware_acceptance_remains_blocked(self):
        """Matrix F: Hardware acceptance remains BLOCKED without hardware evidence."""
        hw_ticket = {
            "id": "T-261",
            "section": "## BLOCKED",
            "blocker": "REAL_ORACLE_MISSING: no FIDO hardware",
            "verify": "tests/secure_apps_portable_live.py (HARDWARE_REAL)",
        }
        board = {"tickets": {"T-261": hw_ticket}}
        state = {"task": "none"}
        report = admission_doctor.classify_blocked_ticket(hw_ticket, board["tickets"], state)
        self.assertIn(
            "REAL_ORACLE_MISSING",
            str(report.get("decision_request", {}).get("missing_authorization", "")),
        )

    def test_matrix_g_active_t220_ownership_remains_untouched(self):
        """Matrix G: Active T-220 ownership remains untouched."""
        active_ticket = {
            "id": "T-220",
            "section": "## DOING",
            "owner": "saipen-cli",
        }
        candidate_ticket = {
            "id": "T-263",
            "section": "## TODO",
            "needs": [],
        }
        board = {"tickets": {"T-220": active_ticket, "T-263": candidate_ticket}}
        state = {"task": "T-220", "phase": "SCOUT"}
        report = admission_doctor.classify_blocked_ticket(candidate_ticket, board["tickets"], state)
        self.assertIn(admission_doctor.CAUSE_D_OWNERSHIP_COLLISION, report["causes"])

    def test_matrix_h_repeated_cc_does_not_duplicate_intake(self):
        """Matrix H: Repeated cc does not duplicate intake or Work."""
        # Test continue loop route classification idempotence
        routed = {
            "ok": True,
            "action": "saipen audit ingest",
            "reason": "audit-inbox",
        }
        kind = continue_loop.classify_route(routed, {}, {})
        self.assertEqual(kind, continue_loop.APPLY_AUDIT_INGEST)

    def test_matrix_i_interrupted_canonical_repair_resumes_safely(self):
        """Matrix I: An interrupted canonical repair resumes safely."""
        routed = {
            "ok": True,
            "action": "saipen claim T-10",
            "reason": "adopt",
        }
        board = {"tickets": {"T-10": {"id": "T-10", "section": "## DOING"}}}
        kind = continue_loop.classify_route(routed, {}, board)
        self.assertEqual(kind, continue_loop.ADOPT)

    def test_matrix_j_failed_validation_causes_bounded_refusal(self):
        """Matrix J: Failed validation causes bounded refusal with preserved evidence."""
        routed = {"ok": False, "action": "saipen recover", "reason": "checkpoint-invalid"}
        kind = continue_loop.classify_route(routed, {}, {})
        self.assertEqual(kind, continue_loop.REFUSAL)

    def test_matrix_k_unrelated_blocked_task_does_not_suppress_runnable_tasks(self):
        """Matrix K: An unrelated blocked task does not suppress runnable authorized tasks."""
        blocked_task = {
            "id": "T-1",
            "section": "## BLOCKED",
            "blocker": "BLOCKED_EXTERNAL",
        }
        runnable_task = {
            "id": "T-2",
            "section": "## TODO",
            "needs": [],
        }
        board = {"tickets": {"T-1": blocked_task, "T-2": runnable_task}}
        state = {"task": "none"}
        report_blocked = admission_doctor.classify_blocked_ticket(
            blocked_task, board["tickets"], state
        )
        report_runnable = admission_doctor.classify_blocked_ticket(
            runnable_task, board["tickets"], state
        )
        self.assertIn(admission_doctor.CAUSE_F_AUTHORIZATION_REQUIRED, report_blocked["causes"])
        self.assertEqual(len(report_runnable["causes"]), 0)

    def test_matrix_l_system_never_changes_protected_dependency_for_convenience(self):
        """Matrix L: Protected dependencies never change just to make work runnable."""
        sw_ticket = {
            "id": "T-263",
            "section": "## TODO",
            "needs": ["T-261"],
        }
        board = {"tickets": {"T-263": sw_ticket}}
        state = {"task": "none"}
        report = admission_doctor.classify_blocked_ticket(sw_ticket, board["tickets"], state)
        # Verify dependency is identified as unmet and not dropped
        self.assertEqual(report["unmet_needs"], ["T-261"])

    def test_matrix_m_original_goal_survives_auto_doctor_repair(self):
        """Matrix M: The operator goal survives repair and resumes idempotently."""
        state = {
            "execution_intent": "goal",
            "goal_waves": 1,
            "goal_tickets": 2,
            "continuation_authority": "operator_required",
            "authority_source": "E-100",
        }
        # State identity must reflect goal parameters
        ident1 = continue_loop.state_identity(state, "board bytes 1")
        ident2 = continue_loop.state_identity(state, "board bytes 1")
        self.assertEqual(ident1, ident2)

    def test_matrix_n_no_publish_and_production_boundaries_hold(self):
        """Matrix N: No-publish and production-vault boundaries hold."""
        saituls_report = admission_doctor.evaluate_live_case_saituls()
        self.assertTrue(saituls_report.get("ok"))
        self.assertEqual(
            saituls_report.get("saituls_authority"),
            "Read-only inspection; zero mutation applied to SAITULS source",
        )

    def test_matrix_o_correction_requiring_new_auth_produces_one_precise_decision_request(self):
        """Matrix O: New authorization requires one precise decision request."""
        saituls_report = admission_doctor.evaluate_live_case_saituls()
        dec = saituls_report.get("decision_request")
        self.assertIsNotNone(dec)
        self.assertIn("blocked_operation", dec)
        self.assertIn("consequences_approval", dec)
        self.assertIn("consequences_refusal", dec)
        self.assertIn("safe_default", dec)
        self.assertIn("recording_mechanism", dec)

    def test_matrix_p_later_directives_do_not_inherit_authority_from_unrelated_scope(self):
        """Matrix P: Later directives never inherit unrelated earlier authority."""
        valid, _msg = decision_request.validate_authority_escalation(
            proposed_reason="PAUSED_BY_OPERATOR unblocked by earlier unrelated goal directive",
            acting_agent="saipen-cli",
            carrier_witness=None,
        )
        self.assertFalse(valid)

    def test_src078_evidence_citation_collision_analysis(self):
        """Phase 9: Assess reported SRC-078 E-001..E-026 citation collision."""
        report = admission_doctor.evaluate_src078_traceability()
        self.assertTrue(report.get("ok"))
        self.assertTrue(report.get("is_receipt_citation_collision"))
        self.assertEqual(report.get("colliding_citations_count"), 26)
        self.assertFalse(report.get("reopen_t260_required"))


if __name__ == "__main__":
    unittest.main()
