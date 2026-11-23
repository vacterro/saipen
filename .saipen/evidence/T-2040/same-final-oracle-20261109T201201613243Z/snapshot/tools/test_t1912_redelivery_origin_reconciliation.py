"""T-1912 / SRC-324 Gap D: admit_host_ingress re-delivery origin reconciliation.

Defect: admit_host_ingress returned the cached unsealed ingress record for a
re-delivered message_id without considering the newly supplied operator_origin,
so the envelope stayed unsealed forever.

Controls:
1. A re-delivery with a genuinely verified origin seals the existing record
   without creating a second ingress or a second budget renewal.
2. Forged, expired, consumed or mismatched-event proofs refuse and leave
   the record byte-identical.
3. A crash between verification and write leaves no half-sealed record.
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

from saipen_engine import host_authority_client, operator_task  # noqa: E402
from saipen_engine.paths import project_identity, project_lineage_identity  # noqa: E402


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RedeliveryOriginReconciliationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="t1912-reconcile-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        # Create minimal .saipen structure
        (self.root / ".saipen").mkdir(parents=True, exist_ok=True)
        (self.root / ".saipen" / "STATE.md").write_text("# STATE\n", encoding="utf-8")

        self.text = "cc all"
        self.digest = _digest(self.text)
        self.session = "session-t1912"
        self.message_id = "msg-turn-1912"
        self.project_id = project_identity(self.root)
        self.lineage = project_lineage_identity(self.root)

    def _valid_proof(self):
        return {
            "schema": 1,
            "kind": "operator-origin",
            "host": "zaicode",
            "nonce": "nonce-t1912",
            "action": "continue",
            "event_id": self.message_id,
            "request_digest": self.digest,
            "session": self.session,
            "project": self.project_id,
            "lineage": self.lineage,
        }

    def _ingress_files(self):
        ingress_dir = self.root / ".saipen" / "cache" / "ingress"
        if not ingress_dir.exists():
            return []
        return sorted(list(ingress_dir.glob("*.json")))

    def test_redelivery_with_verified_origin_seals_existing_record(self):
        # 1. First delivery without operator_origin
        unsealed_payload = {
            "message_id": self.message_id,
            "request_text": self.text,
            "request_digest": self.digest,
            "session_id": self.session,
        }
        res1 = operator_task.admit_host_ingress(unsealed_payload, self.root)
        self.assertTrue(res1.get("ok"), res1)
        self.assertFalse(res1.get("sealed"))

        files = self._ingress_files()
        self.assertEqual(len(files), 1)
        record_before = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertNotIn("operator_origin", record_before)
        self.assertEqual(record_before["witness"], operator_task.WITNESS_MODEL)

        # 2. Re-delivery with genuinely verified operator_origin
        proof = self._valid_proof()
        sealed_payload = dict(unsealed_payload)
        sealed_payload["operator_origin"] = proof

        with mock.patch.object(host_authority_client, "verify_operator_origin", return_value=True) as mock_verify:
            res2 = operator_task.admit_host_ingress(sealed_payload, self.root)

        mock_verify.assert_called_once_with(
            proof,
            project=self.root,
            request_digest=self.digest,
            session=self.session,
        )

        self.assertTrue(res2.get("ok"), res2)
        self.assertTrue(res2.get("sealed"))
        self.assertTrue(res2.get("reconciled"))
        self.assertEqual(res2["ingress_id"], res1["ingress_id"])

        # No second ingress created! Exactly one ingress file on disk
        files_after = self._ingress_files()
        self.assertEqual(len(files_after), 1)
        self.assertEqual(files_after[0], files[0])

        record_after = json.loads(files_after[0].read_text(encoding="utf-8"))
        self.assertEqual(record_after["operator_origin"], proof)
        self.assertEqual(record_after["witness"], operator_task.WITNESS_CARRIER)
        self.assertIn("prior_attempt", record_after)
        self.assertEqual(record_after["prior_attempt"]["created_at"], record_before["created_at"])
        self.assertFalse(record_after["prior_attempt"]["sealed"])

    def test_forged_proof_refuses_and_leaves_record_byte_identical(self):
        payload = {
            "message_id": self.message_id,
            "request_text": self.text,
            "request_digest": self.digest,
            "session_id": self.session,
        }
        operator_task.admit_host_ingress(payload, self.root)
        files = self._ingress_files()
        bytes_before = files[0].read_bytes()

        forged_proof = self._valid_proof()
        forged_payload = dict(payload, operator_origin=forged_proof)

        with mock.patch.object(host_authority_client, "verify_operator_origin", return_value=False):
            res = operator_task.admit_host_ingress(forged_payload, self.root)

        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "INGRESS_ORIGIN_REFUSED")
        bytes_after = files[0].read_bytes()
        self.assertEqual(bytes_before, bytes_after, "File must remain byte-identical on forged origin")

    def test_mismatched_event_refuses_and_leaves_record_byte_identical(self):
        payload = {
            "message_id": self.message_id,
            "request_text": self.text,
            "request_digest": self.digest,
            "session_id": self.session,
        }
        operator_task.admit_host_ingress(payload, self.root)
        files = self._ingress_files()
        bytes_before = files[0].read_bytes()

        mismatched_proof = self._valid_proof()
        mismatched_proof["event_id"] = "different-turn-id"
        mismatched_payload = dict(payload, operator_origin=mismatched_proof)

        with mock.patch.object(host_authority_client, "verify_operator_origin", return_value=True):
            res = operator_task.admit_host_ingress(mismatched_payload, self.root)

        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), operator_task.CODE_MISMATCH)
        self.assertEqual(bytes_before, files[0].read_bytes(), "File must remain byte-identical on event mismatch")

    def test_mismatched_digest_refuses_and_leaves_record_byte_identical(self):
        payload = {
            "message_id": self.message_id,
            "request_text": self.text,
            "request_digest": self.digest,
            "session_id": self.session,
        }
        operator_task.admit_host_ingress(payload, self.root)
        files = self._ingress_files()
        bytes_before = files[0].read_bytes()

        mismatched_proof = self._valid_proof()
        mismatched_proof["request_digest"] = _digest("different text")
        mismatched_payload = dict(payload, operator_origin=mismatched_proof)

        with mock.patch.object(host_authority_client, "verify_operator_origin", return_value=True):
            res = operator_task.admit_host_ingress(mismatched_payload, self.root)

        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), operator_task.CODE_MISMATCH)
        self.assertEqual(bytes_before, files[0].read_bytes())

    def test_mismatched_session_refuses_and_leaves_record_byte_identical(self):
        payload = {
            "message_id": self.message_id,
            "request_text": self.text,
            "request_digest": self.digest,
            "session_id": self.session,
        }
        operator_task.admit_host_ingress(payload, self.root)
        files = self._ingress_files()
        bytes_before = files[0].read_bytes()

        mismatched_proof = self._valid_proof()
        mismatched_proof["session"] = "foreign-session"
        mismatched_payload = dict(payload, operator_origin=mismatched_proof)

        with mock.patch.object(host_authority_client, "verify_operator_origin", return_value=True):
            res = operator_task.admit_host_ingress(mismatched_payload, self.root)

        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), operator_task.CODE_CARRIER_INVALID)
        self.assertEqual(bytes_before, files[0].read_bytes())

    def test_consumed_event_refuses_upgrade_and_leaves_record_byte_identical(self):
        payload = {
            "message_id": self.message_id,
            "request_text": self.text,
            "request_digest": self.digest,
            "session_id": self.session,
        }
        operator_task.admit_host_ingress(payload, self.root)
        files = self._ingress_files()
        # Mark as consumed
        data = json.loads(files[0].read_text(encoding="utf-8"))
        data["consumed"] = True
        files[0].write_text(json.dumps(data, indent=2), encoding="utf-8")
        bytes_before = files[0].read_bytes()

        proof = self._valid_proof()
        sealed_payload = dict(payload, operator_origin=proof)

        with mock.patch.object(host_authority_client, "verify_operator_origin", return_value=True) as mock_verify:
            res = operator_task.admit_host_ingress(sealed_payload, self.root)

        mock_verify.assert_not_called()
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "INGRESS_ORIGIN_REFUSED")
        self.assertEqual(bytes_before, files[0].read_bytes(), "Consumed record must not be upgraded")

    def test_crash_between_verification_and_write_leaves_no_half_sealed_record(self):
        payload = {
            "message_id": self.message_id,
            "request_text": self.text,
            "request_digest": self.digest,
            "session_id": self.session,
        }
        operator_task.admit_host_ingress(payload, self.root)
        files = self._ingress_files()
        bytes_before = files[0].read_bytes()

        proof = self._valid_proof()
        sealed_payload = dict(payload, operator_origin=proof)

        with mock.patch.object(host_authority_client, "verify_operator_origin", return_value=True):
            with mock.patch("os.replace", side_effect=OSError("simulated disk crash")):
                with self.assertRaises(OSError):
                    operator_task.admit_host_ingress(sealed_payload, self.root)

        bytes_after = files[0].read_bytes()
        self.assertEqual(bytes_before, bytes_after, "Original record must remain intact on crash")
        # Ensure no temporary files were leaked
        ingress_dir = self.root / ".saipen" / "cache" / "ingress"
        tmp_files = list(ingress_dir.glob("*.tmp*"))
        self.assertEqual(len(tmp_files), 0, "No half-sealed temporary file may remain")


if __name__ == "__main__":
    unittest.main()
