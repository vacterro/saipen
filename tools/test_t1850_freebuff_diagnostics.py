"""Installed FreeBuff markers identify a diagnostic gap, never operator authority."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import admission_doctor, host_taxonomy, operator_task  # noqa: E402


class FreebuffDiagnostics(unittest.TestCase):
    def test_installed_desktop_marker_is_detected(self):
        # Actual electron/main.cjs spawn env, Desktop 0.0.182; not a trust signal.
        self.assertTrue(operator_task.is_freebuff_host({"FREEBUFF_APP_VERSION": "0.0.182"}))

    def test_other_hosts_and_empty_marker_do_not_match(self):
        for env in ({}, {"FREEBUFF_APP_VERSION": ""}, {"CLAUDECODE": "1"},
                    {"AGENT_HOST": "claude"}, {"SAIPEN_HOST": "codex"}):
            with self.subTest(env=env):
                self.assertFalse(operator_task.is_freebuff_host(env))
        self.assertTrue(operator_task.is_freebuff_host({"FREEBUFF_SESSION": "legacy"}))

    def test_real_marker_reports_missing_origin_without_granting_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            witness = operator_task.witness(
                "continue approved work", env={"FREEBUFF_APP_VERSION": "0.0.182"}, root=root,
            )
            self.assertEqual(witness.get("host_identity"), "freebuff")
            self.assertTrue(witness.get("freebuff_provenance_missing"))
            self.assertEqual(witness.get("diagnostic_code"),
                             operator_task.CODE_FREEBUFF_PROVENANCE_MISSING)
            authority = operator_task.authority_for_provenance(witness, root=root)
            self.assertEqual(authority["witness"], operator_task.WITNESS_MODEL)
            for capability in ("user_explicit", "preempt_active_work", "goal_pivot",
                               "reset_bounded_authority", "external_action"):
                self.assertFalse(authority[capability], capability)

    def test_actual_model_written_carriers_do_not_authenticate_the_marker(self):
        text = "model-written approval"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "task.txt"
            task.write_text(text, encoding="utf-8")
            for carrier in (
                {operator_task.ENV_TASK_SHA256: hashlib.sha256(text.encode()).hexdigest()},
                {operator_task.ENV_TASK_FILE: str(task)},
            ):
                with self.subTest(carrier=next(iter(carrier))):
                    witness = operator_task.witness(
                        text, env={"FREEBUFF_APP_VERSION": "0.0.182", **carrier}, root=root,
                    )
                    self.assertEqual(witness["witness"], operator_task.WITNESS_MODEL)
                    self.assertEqual(witness.get("carrier_integrity"), "MATCHED")
                    self.assertTrue(witness.get("freebuff_provenance_missing"))
                    self.assertFalse(operator_task.authority_for_provenance(
                        witness, root=root,
                    )["user_explicit"])

    def test_missing_origin_has_registered_policy_and_native_recovery(self):
        code = operator_task.CODE_FREEBUFF_PROVENANCE_MISSING
        self.assertTrue(host_taxonomy.known(code))
        problem = host_taxonomy.problem("operator_ingress", code, "native event unavailable")
        self.assertEqual(host_taxonomy.decide("strict", [problem]), "BLOCK")
        self.assertEqual(host_taxonomy.decide("degraded", [problem]), "ALLOW_DEGRADED")
        row = host_taxonomy.get(code)
        self.assertFalse(row.recoverable)  # A carrier cannot be repaired by inventing identity.
        self.assertIn("native", row.operator_action.lower())
        self.assertIn("authority", row.fallback.lower())

    def test_doctor_requests_native_event_proof_and_preserves_original_work(self):
        ticket = {"id": "T-1479", "request_witness": "model_supplied"}
        state = {"phase": "SCOUT", "task": "T-1479", "authority_source": "E-8",
                 "continuation_authority": "operator_required", "safety_valve_mode": "hard_wait"}
        before = copy.deepcopy((ticket, state))
        diagnosis = admission_doctor.classify_blocked_ticket(ticket, {"T-1479": ticket}, state)
        self.assertIn(admission_doctor.CAUSE_E_PROVENANCE_INSUFFICIENT, diagnosis["causes"])
        request = diagnosis["decision_request"]
        self.assertIn("native", request["missing_authorization"].lower())
        self.assertIn("broker", request["recording_mechanism"].lower())
        self.assertIn("worker", request["recording_mechanism"].lower())
        self.assertIn("hard_wait", request["safe_default"])
        self.assertEqual(request["blocked_operation"], "PHASE SCOUT T-1479")
        self.assertEqual((ticket, state), before)


if __name__ == "__main__":
    unittest.main()
