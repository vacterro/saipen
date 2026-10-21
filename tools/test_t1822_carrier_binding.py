"""T-1822: an operator carrier belongs to the session that delivered it.

SRC-280 reports that a real FreeBuff ``cc`` reaches the engine as
``model_supplied`` because the FreeBuff-side transport (a launcher-exported
``SAIPEN_TASK_FILE``/``SAIPEN_TASK_SHA256``, or a host ingress envelope) is not
installed. That transport is a host obligation this repository cannot satisfy,
so T-1822 fixes the side it owns: what the engine does with a carrier once one
arrives.

Two defects were measured before the fix, and both are pinned here:

1. ``operator_task.witness`` called ``active_host_ingress(root)`` with no
   session filter. An envelope stamped ``session_id=session-A`` was consumed by
   session B whenever B supplied the same text, and
   ``authority_for_provenance`` returned ``user_explicit: True``. A replayed
   carrier earned the operator's authority -- the opposite of the refusal the
   ticket promises.

2. ``admit_host_ingress`` named envelopes ``ing-<digest16>``, a function of the
   request TEXT only. Two sessions delivering the same words shared one path and
   the later write replaced the earlier envelope, including its ``session_id``
   and ``message_id``. That is silent destruction of the operator's own record.

The safe failure is ``HOST_PROVENANCE_UNAVAILABLE``: the bytes match an
envelope, but this session cannot prove it delivered them. It is a refusal, not
a promotion and not a crash.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from saipen_engine import host_authority_client, operator_task  # noqa: E402
import test_t1844_origin_broker as origin_controls  # noqa: E402


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CarrierBindingTests(unittest.TestCase):
    def setUp(self):
        self.origin = origin_controls.OriginKernelWithSimulatedNativeIdentity()
        self.origin.setUp()
        self.addCleanup(self.origin.doCleanups)
        self.root = self.origin.root

    def _admit(self, text: str, *, message_id: str, session_id: str | None,
               proof=None) -> dict:
        payload = {
            "message_id": message_id,
            "request_text": text,
            "request_digest": _digest(text),
        }
        if session_id is not None:
            payload["session_id"] = session_id
        if proof is not None:
            payload["operator_origin"] = proof
        result = operator_task.admit_host_ingress(payload, self.root)
        self.assertTrue(result.get("ok"), result)
        return result

    def _envelopes(self) -> list[dict]:
        directory = self.root / ".saipen" / "cache" / "ingress"
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))
        ]

    def test_wrong_session_envelope_is_refused_not_promoted(self):
        self._admit("cc all", message_id="m-A", session_id="session-A")
        with mock.patch.dict(os.environ, {"SAIPEN_HOST_SESSION": "session-B"}):
            witness = operator_task.witness("cc all", root=self.root)
        self.assertEqual(
            witness.get("code"), operator_task.CODE_HOST_PROVENANCE_UNAVAILABLE, witness
        )
        self.assertNotIn("witness", witness)
        self.assertEqual(witness.get("carrier_session"), "session-A")
        self.assertEqual(witness.get("delivering_session"), "session-B")

    def test_refused_replay_leaves_the_owner_envelope_unconsumed(self):
        self._admit("cc all", message_id="m-A", session_id="session-A")
        with mock.patch.dict(os.environ, {"SAIPEN_HOST_SESSION": "session-B"}):
            operator_task.witness("cc all", root=self.root)
        self.assertFalse(self._envelopes()[0].get("consumed"))

    def test_delivering_session_still_earns_operator_authority(self):
        # Session integrity alone is not human origin. The isolated issuer
        # authenticates this positive; no actual host/UI positive is claimed.
        proof = self.origin.issue(text="cc all", action="continue")
        self.origin.register(proof)
        self._admit("cc all", message_id="m-A", session_id="session-A", proof=proof)
        with mock.patch.dict(os.environ, {"SAIPEN_HOST_SESSION": "session-A"}), \
                mock.patch.object(host_authority_client, "_call", side_effect=self.origin.bridge):
            witness = operator_task.witness("cc all", root=self.root)
            self.assertEqual(witness.get("witness"), operator_task.WITNESS_CARRIER, witness)
            self.assertEqual(witness.get("session_id"), "session-A")
            self.assertTrue(operator_task.authority_for_provenance(
                witness, root=self.root,
            )["user_explicit"])

    def test_same_text_from_two_sessions_keeps_both_envelopes(self):
        first = self._admit("cc all", message_id="m-A", session_id="session-A")
        second = self._admit("cc all", message_id="m-B", session_id="session-B")
        self.assertNotEqual(first["ingress_id"], second["ingress_id"])
        stored = self._envelopes()
        self.assertEqual(len(stored), 2)
        self.assertEqual({item["message_id"] for item in stored}, {"m-A", "m-B"})
        self.assertEqual({item["session_id"] for item in stored}, {"session-A", "session-B"})

    def test_redelivery_of_one_message_is_idempotent(self):
        first = self._admit("cc all", message_id="m-A", session_id="session-A")
        second = self._admit("cc all", message_id="m-A", session_id="session-A")
        self.assertEqual(first["ingress_id"], second["ingress_id"])
        self.assertEqual(len(self._envelopes()), 1)

    def test_unnamed_legacy_envelope_stays_admissible(self):
        self._admit("legacy request", message_id="m-legacy", session_id=None)
        with mock.patch.dict(os.environ, {"SAIPEN_HOST_SESSION": "session-Z"}):
            witness = operator_task.witness("legacy request", root=self.root)
        self.assertEqual(witness.get("witness"), operator_task.WITNESS_MODEL, witness)
        self.assertEqual(witness.get("carrier_integrity"), "MATCHED")
        authority = operator_task.authority_for_provenance(witness, root=self.root)
        self.assertTrue(authority["capture"])
        self.assertTrue(authority["local_work"])
        self.assertFalse(authority["user_explicit"])

    def test_no_carrier_at_all_still_reports_model_supplied(self):
        with mock.patch.dict(os.environ, {"SAIPEN_HOST_SESSION": "session-B"}):
            witness = operator_task.witness("nobody delivered this", root=self.root)
        self.assertEqual(witness.get("witness"), operator_task.WITNESS_MODEL)
        self.assertFalse(operator_task.authority_for_provenance(witness)["user_explicit"])

    def test_safe_failure_code_is_the_one_src_280_names(self):
        self.assertEqual(
            operator_task.CODE_HOST_PROVENANCE_UNAVAILABLE, "HOST_PROVENANCE_UNAVAILABLE"
        )


if __name__ == "__main__":
    unittest.main()
