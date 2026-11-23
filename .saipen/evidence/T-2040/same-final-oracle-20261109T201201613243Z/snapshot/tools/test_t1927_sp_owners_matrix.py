"""T-1927 / SRC-333: SP-01..SP-05 production owners matrix verification.

Controls:
1. SP-01: Stage-bound ingress admission, typed classification, and consumption tracking.
2. SP-02: Fresh cc preserves broker scope; stale, forged or model-supplied ingress caches never mint or renew authority.
3. SP-03: Bounded canonical WAIT recovery terminates with a typed action (TURN_OPERATOR_WAIT) without unbounded loop.
4. SP-04: SAIMAIL telegrams mailbox retrieval is causal and bounded; header counts only, never promoting cross-project text as command or state.
5. SP-05: Response provenance and verification cycle isolation: active ticket verification requires a fresh current-cycle VERIFY boundary and conf: high PASS; historical board state or unrelated tickets never satisfy verification.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import cold_recovery, host_authority_client, operator_task, telegrams  # noqa: E402
from saipen_engine.log import NO_VERIFY_BOUNDARY, verification_evidence  # noqa: E402
from saipen_engine.paths import project_identity, project_lineage_identity  # noqa: E402


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SPOwnersMatrixTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="t1927-matrix-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".saipen").mkdir(parents=True, exist_ok=True)
        (self.root / ".saipen" / "STATE.md").write_text("# STATE\n", encoding="utf-8")

        self.text = "cc all"
        self.digest = _digest(self.text)
        self.session = "session-t1927"
        self.message_id = "msg-turn-1927"
        self.project_id = project_identity(self.root)
        self.lineage = project_lineage_identity(self.root)

    def _valid_proof(self):
        return {
            "schema": 1,
            "kind": "operator-origin",
            "host": "zaicode",
            "nonce": "nonce-t1927",
            "event_id": self.message_id,
            "request_digest": self.digest,
            "session": self.session,
            "project": self.project_id,
            "lineage": self.lineage,
            "expiry_epoch_s": 9999999999,
            "issued_epoch_s": 1000000000,
            "worker_pid": 1234,
        }

    def test_sp01_and_sp02_ingress_broker_scope_and_consumption(self):
        # SP-01 & SP-02: Fresh ingress with broker-verified proof is admitted and sealed
        proof = self._valid_proof()
        ingress_data = {
            "request_text": self.text,
            "request_digest": self.digest,
            "session_id": self.session,
            "message_id": self.message_id,
            "operator_origin": proof,
            "project_lineage": self.lineage,
        }
        with (
            mock.patch.object(host_authority_client, "verify_operator_origin", return_value=True),
            mock.patch.object(host_authority_client, "verify_record", return_value=True),
        ):
            admitted = operator_task.admit_host_ingress(ingress_data, self.root)
            self.assertTrue(admitted.get("ok"), admitted)
            self.assertTrue(admitted.get("sealed"))
            self.assertEqual(admitted.get("destination_op"), "continue")

            # Check written record in active_host_ingress
            records = operator_task.active_host_ingress(self.root, include_consumed=True)
            self.assertEqual(len(records), 1)
            self.assertFalse(records[0].get("consumed"))
            self.assertEqual(records[0].get("witness"), operator_task.WITNESS_CARRIER)

            # Consume the ingress
            ingress_id = records[0]["ingress_id"]
            consumed = operator_task.consume_host_ingress(self.root, ingress_id, "test-worker")
            self.assertTrue(consumed)

            # Once consumed, it is excluded from unconsumed active_host_ingress
            unconsumed = operator_task.active_host_ingress(self.root, include_consumed=False)
            self.assertEqual(len(unconsumed), 0)

            # An unsealed ingress, once consumed, cannot be upgraded with a new origin (SRC-324 Gap D / SP-02)
            msg_unsealed = "msg-unsealed-consume"
            unsealed_res = operator_task.admit_host_ingress(
                {
                    "request_text": self.text,
                    "request_digest": self.digest,
                    "session_id": self.session,
                    "message_id": msg_unsealed,
                    "operator_origin": None,
                    "project_lineage": self.lineage,
                },
                self.root,
            )
            self.assertTrue(unsealed_res.get("ok"))
            unsealed_id = unsealed_res["ingress_id"]
            self.assertTrue(operator_task.consume_host_ingress(self.root, unsealed_id, "test-worker"))

            upgrade_attempt = operator_task.admit_host_ingress(
                {
                    "request_text": self.text,
                    "request_digest": self.digest,
                    "session_id": self.session,
                    "message_id": msg_unsealed,
                    "operator_origin": proof,
                    "project_lineage": self.lineage,
                },
                self.root,
            )
            self.assertFalse(upgrade_attempt.get("ok"))
            self.assertEqual(upgrade_attempt.get("code"), "INGRESS_ORIGIN_REFUSED")
            self.assertIn("consumed ingress cannot be upgraded", upgrade_attempt.get("detail", ""))

    def test_sp02_stale_or_forged_or_model_witness_never_renews_authority(self):
        # SP-02: Model-supplied ingress without proof is admitted but unsealed
        unsealed = operator_task.admit_host_ingress(
            {
                "request_text": self.text,
                "request_digest": self.digest,
                "session_id": self.session,
                "message_id": "msg-unsealed",
                "operator_origin": None,
                "project_lineage": self.lineage,
            },
            self.root,
        )
        self.assertTrue(unsealed.get("ok"))
        self.assertFalse(unsealed.get("sealed"))

        # Forged proof fails verification: broker refuses origin
        forged = self._valid_proof()
        forged["event_id"] = "msg-unsealed"
        with mock.patch.object(host_authority_client, "verify_operator_origin", return_value=False):
            refused = operator_task.admit_host_ingress(
                {
                    "request_text": self.text,
                    "request_digest": self.digest,
                    "session_id": self.session,
                    "message_id": "msg-unsealed",
                    "operator_origin": forged,
                    "project_lineage": self.lineage,
                },
                self.root,
            )
            self.assertFalse(refused.get("ok"))
            self.assertEqual(refused.get("code"), "INGRESS_ORIGIN_REFUSED")

    def test_sp03_stable_wait_terminates_with_typed_action(self):
        # SP-03: Canonical next action WAIT must resolve to TURN_OPERATOR_WAIT
        # and not kick off an unbounded command loop.
        recall = {
            "readable": True,
            "wait": True,
            "continuation_required": False,
        }
        res = cold_recovery.turn_entry(recall, cold_recovery.INGRESS_CONTINUATION)
        self.assertEqual(res["decision"], cold_recovery.TURN_OPERATOR_WAIT)
        self.assertFalse(res["kick"])
        self.assertIsNone(res["command"])
        self.assertIn("operator WAIT", res["reason"])

    def test_sp04_mailbox_retrieval_bounded_and_isolated(self):
        # SP-04: Unconfigured or missing mailbox returns structured state without throwing
        # or promoting cross-project text into project state.
        with mock.patch("saipen_engine.mailbox.bound_workspace", return_value=None):
            result = telegrams.turn_entry(self.root, {"agent": "saipen-cli"})
            self.assertEqual(result["state"], telegrams.STATE_NOT_CONFIGURED)
            self.assertIn("saipen mail init", result["detail"])

    def test_sp05_response_provenance_and_verification_cycle_isolation(self):
        # SP-05: Unrelated receipts and historical board state never support verification
        # 1. Missing verify boundary fails with NO_VERIFY_BOUNDARY
        events_no_boundary = [
            {"event": 1, "ticket": "T-100", "taxonomy": "DEC", "text": "ticket added via SAIOPS"},
            {"event": 2, "ticket": "T-100", "taxonomy": "RUN", "text": "build -> done"},
            {"event": 3, "ticket": "T-100", "taxonomy": "RUN", "text": "verify -> PASS conf: high"},
        ]
        ok, reason = verification_evidence("T-100", events_no_boundary)
        self.assertFalse(ok)
        self.assertEqual(reason, NO_VERIFY_BOUNDARY)

        # 2. Cross-ticket events cannot satisfy T-100
        events_cross_ticket = [
            {"event": 1, "ticket": "T-100", "taxonomy": "RUN", "text": "transition to VERIFY"},
            {"event": 2, "ticket": "T-200", "taxonomy": "RUN", "text": "verify -> PASS conf: high"},
        ]
        ok, reason = verification_evidence("T-100", events_cross_ticket)
        self.assertFalse(ok)

        # 3. Low confidence PASS fails verification
        events_low_conf = [
            {"event": 1, "ticket": "T-100", "taxonomy": "RUN", "text": "transition to VERIFY"},
            {"event": 2, "ticket": "T-100", "taxonomy": "RUN", "text": "verify -> PASS conf: low"},
        ]
        ok, reason = verification_evidence("T-100", events_low_conf)
        self.assertFalse(ok)

        # 4. Valid current-cycle high confidence PASS succeeds
        events_valid = [
            {"event": 1, "ticket": "T-100", "taxonomy": "RUN", "text": "transition to VERIFY"},
            {"event": 2, "ticket": "T-100", "taxonomy": "RUN", "text": "verify -> PASS conf: high [target: T-100]"},
        ]
        ok, reason = verification_evidence("T-100", events_valid)
        self.assertTrue(ok)
        self.assertIn("conf: high", reason)


if __name__ == "__main__":
    unittest.main()
