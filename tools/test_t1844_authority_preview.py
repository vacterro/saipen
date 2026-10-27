"""Authority previews must identify the same native event as capture.

The native identity/process facts are explicitly simulated by the existing
isolated broker fixture; these tests claim no actual host or UI acceptance.
"""

from __future__ import annotations

import copy
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from saipen_engine import handoff, intake, operations, operator_task as OT
from saipen_engine import host_authority_client as HC
from saipen_engine.pending_ingress import ingress_digest
import test_t1844_origin_broker as controls
from test_hermetic_env import isolate_host_session

TEXT = f"{handoff.GRANT_HEADER}\nT-1 -> next-agent\n{handoff.GRANT_TERMINATOR}\n"


def setUpModule():
    isolate_host_session()


class AuthorityPreviewEvents(unittest.TestCase):
    def setUp(self):
        self.origin = controls.OriginKernelWithSimulatedNativeIdentity()
        self.origin.setUp()
        self.addCleanup(self.origin.doCleanups)
        self.root = self.origin.root

    def capture(self, proof=None):
        provenance = None if proof is None else {
            "witness": OT.WITNESS_CARRIER,
            "declared_by": OT.DECLARED_HOST_INGRESS,
            "compared_digest": ingress_digest(TEXT),
            "operator_origin": proof,
        }
        result = intake.capture(
            self.root, TEXT, source_kind="user_instruction",
            projection_policy=intake.PROJECTION_AUTHORITY_ONLY,
            request_provenance=provenance,
        )
        self.assertTrue(result["ok"], result)
        return result["receipt"]

    def offer(self, proof, *, worker=20):
        self.origin.register(proof, worker=worker)
        self.origin.peer = SimpleNamespace(pid=worker)
        result = OT.admit_host_ingress({
            "request_text": TEXT, "session_id": "session-A",
            "message_id": proof["event_id"], "operator_origin": proof,
        }, self.root)
        self.assertTrue(result["ok"], result)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def preview(self):
        before = self.snapshot()
        records = copy.deepcopy(self.origin.broker.origins.records)
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), \
                mock.patch.object(HC, "_call", side_effect=self.origin.bridge):
            result = operations.authority_capture(self.root, "fixture", TEXT, dry_run=True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.origin.broker.origins.records, records)
        self.assertTrue(result.ok, result.to_dict())
        return result

    def test_fresh_native_preview_does_not_reuse_an_older_model_receipt(self):
        old = self.capture()
        old_meta = intake._read_meta(self.root, old)
        proof = self.origin.issue(action="handoff", text=TEXT)
        self.offer(proof)
        self.assertIsNone(self.preview().data["receipt"])
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), \
                mock.patch.object(HC, "_call", side_effect=self.origin.bridge):
            captured = operations.authority_capture(self.root, "fixture", TEXT)
        self.assertTrue(captured.ok, captured.to_dict())
        self.assertNotEqual(captured.data["receipt"], old)
        self.assertEqual(intake._read_meta(self.root, old), old_meta)
        self.assertEqual(self.preview().data["receipt"], captured.data["receipt"])

    def test_preview_selects_the_current_native_event_without_binding_it(self):
        first = self.origin.issue(action="handoff", text=TEXT)
        old = self.capture(first)
        second = self.origin.issue(action="handoff", text=TEXT, event="second-event")
        current = self.capture(second)
        self.assertNotEqual(old, current)
        self.offer(second, worker=40)
        self.assertEqual(self.preview().data["receipt"], current)
        self.assertIsNone(self.origin.broker.origins.records[second["nonce"]]["receipt"])

    def test_preview_preserves_the_real_capture_fidelity_refusal(self):
        before = self.snapshot()
        with mock.patch.dict(os.environ, {OT.ENV_TASK_SHA256: "0" * 64}):
            preview = operations.authority_capture(self.root, "fixture", TEXT, dry_run=True)
            actual = operations.authority_capture(self.root, "fixture", TEXT)
        self.assertFalse(preview.ok, preview.to_dict())
        self.assertEqual(preview.code, OT.CODE_MISMATCH)
        self.assertEqual(preview.code, actual.code)
        self.assertEqual(self.snapshot(), before)

    def test_preview_refuses_corruption_before_filtering_out_an_older_event(self):
        old = self.capture()
        (self.root / f".saipen/intake/active/{old}.md").write_text(
            "changed source", encoding="utf-8",
        )
        self.offer(self.origin.issue(action="handoff", text=TEXT))
        before = self.snapshot()
        records = copy.deepcopy(self.origin.broker.origins.records)
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), \
                mock.patch.object(HC, "_call", side_effect=self.origin.bridge):
            preview = operations.authority_capture(self.root, "fixture", TEXT, dry_run=True)
        self.assertFalse(preview.ok, preview.to_dict())
        self.assertEqual(preview.code, "SOURCE_CORRUPTION")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.origin.broker.origins.records, records)


if __name__ == "__main__":
    unittest.main()
