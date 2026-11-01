"""AUT31-001 and AUT31-002 Regression Controls (SRC-352).

A01 - A10: Publisher Qualification Provenance Gate Controls (AUT31-001)
B01 - B10: Revision-Scoped Suppression & Legacy Ack Controls (AUT31-002)
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from producer_backends import saipal_adapter as adapter_module
from saipen_engine import audit_enqueue, paths


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _Replay:
    def __init__(self, adapter, rows, *, source_digest):
        self.adapter = adapter
        self.rows = rows
        self.source_digest = source_digest

    def __call__(self, *, page_size):
        identity = {
            "source_digest": self.source_digest,
            "finding_count": len(self.rows),
        }
        yield (0, 1, list(self.rows), identity)


class PublisherProvenanceControlsTests(unittest.TestCase):
    """A01 - A10: Publisher qualification provenance gate controls (AUT31-001)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="aut31-a-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        (self.project / ".saipen" / "campaign").mkdir(parents=True)
        (self.project / ".saipen" / "inbox" / "layers").mkdir(parents=True)
        self.home = self.root / "backend"
        (self.home / "tools").mkdir(parents=True)
        (self.home / ".saipal").mkdir()
        self.adapter = adapter_module.SaipalAdapter(self.home)

    def write_artifact(self, name: str, body: str) -> Path:
        path = self.project / name
        path.write_bytes(body.encode("utf-8"))
        return path

    def finding(self, text: str, *, finding_id="PAL-1", **changes):
        body = f"# Audit {finding_id}\n{text}\n"
        digest = sha256(body)
        f = {
            "finding_id": finding_id,
            "state": "QUALIFIED",
            "audit_body": body,
            "artifact_digest": digest,
        }
        f.update(changes)
        return f

    def test_a01_genuine_receipt_belonging_to_finding_a_used_for_finding_b(self):
        """A01: Genuine receipt belonging to finding A is used for finding B. Refusal, no enqueue."""
        # 1. Qualify and publish PAL-TRUSTED
        body_trusted = "# Audit PAL-TRUSTED\nTrusted body\n"
        digest_trusted = sha256(body_trusted)
        self.adapter.record_qualification(
            self.project,
            "PAL-TRUSTED",
            artifact_digest=digest_trusted,
            publication_scope="project",
        )
        trusted = {
            "finding_id": "PAL-TRUSTED",
            "state": "QUALIFIED",
            "audit_body": body_trusted,
            "artifact_digest": digest_trusted,
            "qualification_receipt": {
                "artifact_path": "audit_trusted.md",
                "artifact_digest": digest_trusted,
                "publication_scope": "project",
            },
        }
        self.write_artifact("audit_trusted.md", body_trusted)
        pub_res = self.adapter.deliver_finding_to_audit_inbox(
            self.project, trusted, publication_authorized=True
        )
        self.assertTrue(pub_res.get("ok"), pub_res)
        real_op_id = pub_res["receipt"]["operation_id"]

        # 2. Try to publish PAL-UNRELATED using PAL-TRUSTED's publication operation ID
        body_unrelated = "# Audit PAL-UNRELATED\nUnrelated body\n"
        digest_unrelated = sha256(body_unrelated)
        unrelated = {
            "finding_id": "PAL-UNRELATED",
            "state": "QUALIFIED",
            "audit_body": body_unrelated,
            "artifact_digest": digest_unrelated,
            "qualification_receipt": real_op_id,
        }
        res = self.adapter.deliver_finding_to_audit_inbox(
            self.project, unrelated, publication_authorized=True
        )
        self.assertFalse(res.get("ok"), res)
        self.assertIn(
            str(res.get("status")),
            {"NOT_QUALIFIED", adapter_module.PROVENANCE_UNVERIFIED},
            res,
        )

    def test_a02_genuine_receipt_with_another_artifact_digest(self):
        """A02: Genuine receipt with another artifact digest. Refusal."""
        body = "# Audit PAL-1\nBody 1\n"
        digest1 = sha256(body)
        qual = self.adapter.record_qualification(
            self.project, "PAL-1", artifact_digest=digest1, publication_scope="project"
        )
        self.assertTrue(qual.get("ok"), qual)
        qual_op_id = qual["record"]["operation_id"]

        # Present qual_op_id for PAL-1 but with different artifact bytes/digest
        different_body = "# Audit PAL-1\nDifferent modified body\n"
        digest2 = sha256(different_body)
        finding = {
            "finding_id": "PAL-1",
            "state": "QUALIFIED",
            "audit_body": different_body,
            "artifact_digest": digest2,
            "qualification_receipt": qual_op_id,
        }
        res = self.adapter.deliver_finding_to_audit_inbox(
            self.project, finding, publication_authorized=True
        )
        self.assertFalse(res.get("ok"), res)
        self.assertIn(
            str(res.get("status")),
            {"NOT_QUALIFIED", adapter_module.PROVENANCE_UNVERIFIED},
            res,
        )

    def test_a03_genuine_receipt_with_another_project_lineage(self):
        """A03: Genuine receipt with another project lineage. Refusal."""
        body = "# Audit PAL-1\nBody 1\n"
        digest = sha256(body)
        qual = self.adapter.record_qualification(
            self.project,
            "PAL-1",
            artifact_digest=digest,
            publication_scope="project",
            project_lineage="lineage-origin-alpha",
        )
        self.assertTrue(qual.get("ok"), qual)
        qual_op_id = qual["record"]["operation_id"]

        finding = {
            "finding_id": "PAL-1",
            "state": "QUALIFIED",
            "audit_body": body,
            "artifact_digest": digest,
            "qualification_receipt": qual_op_id,
            "project_lineage": "lineage-target-beta",  # mismatched lineage
        }
        res = self.adapter.deliver_finding_to_audit_inbox(
            self.project, finding, publication_authorized=True
        )
        self.assertFalse(res.get("ok"), res)
        self.assertIn(
            str(res.get("status")),
            {"NOT_QUALIFIED", adapter_module.PROVENANCE_UNVERIFIED},
            res,
        )

    def test_a04_genuine_receipt_with_another_source_generation(self):
        """A04: Genuine receipt with another source generation. Refusal unless producer revision."""
        body = "# Audit PAL-1\nBody 1\n"
        digest = sha256(body)
        qual = self.adapter.record_qualification(
            self.project,
            "PAL-1",
            artifact_digest=digest,
            publication_scope="project",
            source_generation="gen-100",
        )
        self.assertTrue(qual.get("ok"), qual)
        qual_op_id = qual["record"]["operation_id"]

        # Different generation, not marked revision -> refused
        finding_mismatch = {
            "finding_id": "PAL-1",
            "state": "QUALIFIED",
            "audit_body": body,
            "artifact_digest": digest,
            "qualification_receipt": qual_op_id,
            "source_generation": "gen-200",
        }
        res = self.adapter.deliver_finding_to_audit_inbox(
            self.project, finding_mismatch, publication_authorized=True
        )
        self.assertFalse(res.get("ok"), res)
        self.assertIn(
            str(res.get("status")),
            {"NOT_QUALIFIED", adapter_module.PROVENANCE_UNVERIFIED},
            res,
        )

        # Marked producer_authenticated_revision -> permitted
        finding_rev = {
            "finding_id": "PAL-1",
            "state": "QUALIFIED",
            "audit_body": body,
            "artifact_digest": digest,
            "qualification_receipt": qual_op_id,
            "source_generation": "gen-200",
            "producer_authenticated_revision": True,
        }
        res_rev = self.adapter.deliver_finding_to_audit_inbox(
            self.project, finding_rev, publication_authorized=True
        )
        self.assertTrue(res_rev.get("ok"), res_rev)

    def test_a05_invented_string_receipt(self):
        """A05: Invented string receipt. Refusal."""
        body = "# Audit PAL-1\nBody 1\n"
        digest = sha256(body)
        finding = {
            "finding_id": "PAL-1",
            "state": "QUALIFIED",
            "audit_body": body,
            "artifact_digest": digest,
            "qualification_receipt": "invented-receipt-xyz-999",
        }
        res = self.adapter.deliver_finding_to_audit_inbox(
            self.project, finding, publication_authorized=True
        )
        self.assertFalse(res.get("ok"), res)
        self.assertIn(
            str(res.get("status")),
            {"NOT_QUALIFIED", adapter_module.PROVENANCE_UNVERIFIED},
            res,
        )

    def test_a06_valid_broker_qualified_finding_accepted_exactly_once(self):
        """A06: Valid broker-qualified finding with exact matching evidence accepted exactly once."""
        body = "# Audit PAL-1\nBroker verified body\n"
        digest = sha256(body)
        finding = {
            "finding_id": "PAL-1",
            "state": "QUALIFIED",
            "audit_body": body,
            "artifact_digest": digest,
            "qualification_receipt": {
                "authenticated": True,
                "signature": "broker-sig-123",
                "provenance": "broker-prov-123",
            },
        }
        with mock.patch.object(adapter_module, "_broker_verified", return_value=True):
            res1 = self.adapter.deliver_finding_to_audit_inbox(
                self.project, finding, publication_authorized=True
            )
            self.assertTrue(res1.get("ok"), res1)
            self.assertEqual(res1.get("status"), adapter_module.DELIVERED_PUBLICATION)

            # Second identical delivery is idempotent replay
            res2 = self.adapter.deliver_finding_to_audit_inbox(
                self.project, finding, publication_authorized=True
            )
            self.assertTrue(res2.get("ok"), res2)
            self.assertTrue(res2.get("idempotent_replay") or res2.get("receipt", {}).get("idempotent"))

    def test_a07_valid_producer_artifact_route(self):
        """A07: Valid producer artifact route preserved."""
        body = "# Audit PAL-1\nArtifact body\n"
        digest = sha256(body)
        self.write_artifact("audit_pal1.md", body)
        self.adapter.record_qualification(
            self.project, "PAL-1", artifact_digest=digest, publication_scope="project"
        )
        finding = {
            "finding_id": "PAL-1",
            "state": "QUALIFIED",
            "audit_body": body,
            "artifact_digest": digest,
            "qualification_receipt": {
                "artifact_path": "audit_pal1.md",
                "artifact_digest": digest,
                "publication_scope": "project",
            },
        }
        res = self.adapter.deliver_finding_to_audit_inbox(
            self.project, finding, publication_authorized=True
        )
        self.assertTrue(res.get("ok"), res)

    def test_a08_publication_not_authorized_staged(self):
        """A08: Publication not authorized returns STAGED, no destination write."""
        body = "# Audit PAL-1\nBody\n"
        digest = sha256(body)
        self.write_artifact("audit_pal1.md", body)
        self.adapter.record_qualification(
            self.project, "PAL-1", artifact_digest=digest, publication_scope="project"
        )
        finding = {
            "finding_id": "PAL-1",
            "state": "QUALIFIED",
            "audit_body": body,
            "artifact_digest": digest,
            "qualification_receipt": {
                "artifact_path": "audit_pal1.md",
                "artifact_digest": digest,
                "publication_scope": "project",
            },
        }
        res = self.adapter.deliver_finding_to_audit_inbox(
            self.project, finding, publication_authorized=False
        )
        self.assertFalse(res.get("ok"), res)
        self.assertEqual(res.get("status"), adapter_module.STAGED_PUBLICATION)
        layers = list((self.project / "audit").glob("*.md"))
        self.assertEqual(layers, [], "No layer files should be written when STAGED")

    def test_a09_concurrent_identical_delivery(self):
        """A09: Concurrent identical delivery produces one canonical operation."""
        body = "# Audit PAL-CONCURRENT\nConcurrent body\n"
        digest = sha256(body)
        self.write_artifact("audit_conc.md", body)
        self.adapter.record_qualification(
            self.project, "PAL-CONCURRENT", artifact_digest=digest, publication_scope="project"
        )
        finding = {
            "finding_id": "PAL-CONCURRENT",
            "state": "QUALIFIED",
            "audit_body": body,
            "artifact_digest": digest,
            "qualification_receipt": {
                "artifact_path": "audit_conc.md",
                "artifact_digest": digest,
                "publication_scope": "project",
            },
        }
        results = []

        def worker():
            r = self.adapter.deliver_finding_to_audit_inbox(
                self.project, finding, publication_authorized=True
            )
            results.append(r)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertTrue(r.get("ok"), r)

        receipts = self.adapter.collect_publication_receipts(self.project)
        self.assertTrue(receipts.get("ok"), receipts)
        op_ids = [r.get("operation_id") for r in receipts.get("records", [])]
        self.assertEqual(len(op_ids), 1, "Only one canonical receipt should be recorded")

    def test_a10_crash_after_enqueue_reconciles_receipt(self):
        """A10: Crash after enqueue and before local ack reconciles original receipt."""
        body = "# Audit PAL-RECOVER\nRecover body\n"
        digest = sha256(body)
        self.write_artifact("audit_rec.md", body)
        self.adapter.record_qualification(
            self.project, "PAL-RECOVER", artifact_digest=digest, publication_scope="project"
        )
        finding = {
            "finding_id": "PAL-RECOVER",
            "state": "QUALIFIED",
            "audit_body": body,
            "artifact_digest": digest,
            "qualification_receipt": {
                "artifact_path": "audit_rec.md",
                "artifact_digest": digest,
                "publication_scope": "project",
            },
        }
        # Simulate enqueue succeeding but receipt append failing
        res = audit_enqueue.enqueue(
            self.project,
            producer="saipal",
            body=body,
            producer_operation_id="saipal-pal-recover",
            producer_item_id="PAL-RECOVER",
        )
        self.assertTrue(res.get("ok"), res)

        # Receipt log is empty because it crashed before writing saipal_receipts.jsonl
        reconciled = self.adapter.reconcile_history(self.project, kind="publication_receipts")
        self.assertTrue(reconciled.get("ok"), reconciled)
        self.assertTrue(reconciled.get("repaired"), reconciled)

        receipts = self.adapter.collect_publication_receipts(self.project)
        self.assertTrue(receipts.get("ok"), receipts)
        self.assertEqual(len(receipts.get("records", [])), 1)
        self.assertEqual(receipts["records"][0]["finding_id"], "PAL-RECOVER")


class FindingRevisionControlsTests(unittest.TestCase):
    """B01 - B10: Finding revision identity and legacy ack controls (AUT31-002)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="aut31-b-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".saipen" / "campaign").mkdir(parents=True)
        (self.root / ".saipen" / "inbox" / "layers").mkdir(parents=True)
        self.home = self.root / "backend"
        (self.home / "tools").mkdir(parents=True)
        (self.home / ".saipal").mkdir()
        self.adapter = adapter_module.SaipalAdapter(self.home)

    def finding(self, text: str, *, finding_id="PAL-1", state="QUALIFIED"):
        body = f"# finding\n\n{text}\n"
        artifact_bytes = f"qualification of {finding_id}: {text}\n".encode("utf-8")
        artifact_rel = f"qual-{finding_id}-{text[:10].replace(' ', '-')}.md"
        (self.root / artifact_rel).write_bytes(artifact_bytes)
        artifact_digest = hashlib.sha256(artifact_bytes).hexdigest()
        scope = adapter_module.PUBLICATION_SCOPE_DEFAULT
        self.adapter.record_qualification(
            self.root,
            finding_id,
            artifact_digest=artifact_digest,
            publication_scope=scope,
        )
        return {
            "finding_id": finding_id,
            "state": state,
            "audit_body": body,
            "artifact_digest": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "qualification_receipt": {
                "artifact_path": artifact_rel,
                "artifact_digest": artifact_digest,
                "publication_scope": scope,
            },
        }

    def publish(self, finding):
        return self.adapter.deliver_finding_to_audit_inbox(
            self.root, finding, publication_authorized=True
        )

    def walk(self, rows, *, source_digest="corpus-a"):
        self.adapter.iter_finding_pages = _Replay(self.adapter, rows, source_digest=source_digest)
        pages = list(self.adapter.iter_new_qualified_findings(self.root, page_size=50))
        yielded = []
        for page in pages:
            if not page.get("ok"):
                continue
            yielded.extend(page.get("findings") or [])
        return pages, yielded

    def _append_ack(self, ids, *, source_digest=None):
        record = {
            "schema_version": 1,
            "source_digest": source_digest,
            "finding_ids": list(ids),
            "acknowledged_at": "2026-10-30T00:00:00Z",
        }
        path = self.root / ".saipen" / "campaign" / adapter_module.ACK_JOURNAL_NAME
        with path.open("ab") as stream:
            stream.write((json.dumps(record, sort_keys=True) + "\n").encode("utf-8"))

    def test_b01_old_published_pal1_legacy_ack_changed_new_pal1(self):
        """B01: Old published PAL-1, legacy ack, changed new PAL-1. New revision is not silently omitted."""
        # 1. Qualify and publish PAL-1 with original audit body
        first = self.finding("original body", finding_id="PAL-1")
        published = self.publish(first)
        self.assertTrue(published.get("ok"), published)

        # 2. Append legacy acknowledgment row
        self._append_ack(["PAL-1"], source_digest=None)

        # 3. Create new qualified PAL-1 with materially changed body
        second = self.finding("SUBSTANTIALLY REVISED body", finding_id="PAL-1")

        # 4. Walk in new corpus generation
        _pages, yielded = self.walk([second], source_digest="corpus-generation-2")
        ids = [str(r.get("finding_id")) for r in yielded]
        self.assertEqual(ids, ["PAL-1"], "Revised finding PAL-1 must not be suppressed by legacy ack")

    def test_b02_old_published_pal1_unchanged_identical_replay(self):
        """B02: Old published PAL-1, unchanged identical replay. Safely suppressed."""
        first = self.finding("original body", finding_id="PAL-1")
        self.assertTrue(self.publish(first).get("ok"))
        self._append_ack(["PAL-1"], source_digest=None)

        _pages, yielded = self.walk([first], source_digest="corpus-generation-2")
        ids = [str(r.get("finding_id")) for r in yielded]
        self.assertEqual(ids, [], "Identical replay of PAL-1 must be suppressed")

    def test_b03_legacy_ack_with_no_canonical_destination_receipt(self):
        """B03: Legacy ack with no canonical destination receipt. No unjustified suppression."""
        self._append_ack(["PAL-1"], source_digest=None)
        finding = self.finding("uncommitted finding body", finding_id="PAL-1")

        _pages, yielded = self.walk([finding], source_digest="corpus-1")
        ids = [str(r.get("finding_id")) for r in yielded]
        self.assertEqual(ids, ["PAL-1"], "Uncommitted finding with legacy ack must not be suppressed")

    def test_b04_legacy_ack_for_another_corpus(self):
        """B04: Legacy ack for another corpus. No cross-corpus suppression."""
        self._append_ack(["PAL-1"], source_digest=None)
        finding = self.finding("finding in new corpus", finding_id="PAL-1")

        _pages, yielded = self.walk([finding], source_digest="corpus-brand-new")
        ids = [str(r.get("finding_id")) for r in yielded]
        self.assertEqual(ids, ["PAL-1"])

    def test_b05_scoped_ack_for_current_immutable_version(self):
        """B05: Scoped ack for exactly the current immutable version. Valid suppression."""
        self._append_ack(["PAL-1"], source_digest="corpus-scoped")
        finding = self.finding("body", finding_id="PAL-1")

        _pages, yielded = self.walk([finding], source_digest="corpus-scoped")
        ids = [str(r.get("finding_id")) for r in yielded]
        self.assertEqual(ids, [], "Scoped ack for current corpus must suppress")

    def test_b06_multiple_revisions_under_one_logical_finding(self):
        """B06: Multiple revisions under one logical finding have independent identities."""
        rev1 = self.finding("rev 1 body", finding_id="PAL-1")
        pub1 = self.publish(rev1)
        self.assertTrue(pub1.get("ok"), pub1)

        rev2 = self.finding("rev 2 body", finding_id="PAL-1")
        _pages, yielded = self.walk([rev2], source_digest="corpus-rev-2")
        self.assertEqual(len(yielded), 1)
        self.assertEqual(yielded[0]["artifact_digest"], rev2["artifact_digest"])

    def test_b07_crash_between_page_read_and_delivery(self):
        """B07: Crash between page read and delivery leaves finding pending."""
        finding = self.finding("pending body", finding_id="PAL-1")
        # Reading a page updates cursor watermark, but does not acknowledge finding
        _pages, yielded1 = self.walk([finding], source_digest="corpus-walk")
        self.assertEqual(len(yielded1), 1)

        # Next walk without delivery still yields the finding
        _pages, yielded2 = self.walk([finding], source_digest="corpus-walk")
        self.assertEqual(len(yielded2), 1)

    def test_b08_crash_after_canonical_enqueue_recovers_receipt(self):
        """B08: Crash after canonical enqueue recovers original publication receipt."""
        body = "# PAL-CRASH\nBody\n"
        res = audit_enqueue.enqueue(
            self.root,
            producer="saipal",
            body=body,
            producer_operation_id="saipal-pal-crash",
            producer_item_id="PAL-CRASH",
        )
        self.assertTrue(res.get("ok"), res)
        reconciled = self.adapter.reconcile_history(self.root, kind="publication_receipts")
        self.assertTrue(reconciled.get("ok"), reconciled)
        self.assertTrue(reconciled.get("repaired"), reconciled)

    def test_b09_damaged_legacy_journal_refusal_preserves_bytes(self):
        """B09: Damaged legacy journal results in typed refusal and preserved bytes."""
        path = self.root / ".saipen" / "campaign" / adapter_module.ACK_JOURNAL_NAME
        bad_bytes = b'{"truncated": true\nnot valid json\n'
        path.write_bytes(bad_bytes)

        finding = self.finding("body", finding_id="PAL-1")
        self.adapter.iter_finding_pages = _Replay(self.adapter, [finding], source_digest="corpus-a")
        pages = list(self.adapter.iter_new_qualified_findings(self.root, page_size=50))
        self.assertFalse(pages[0].get("ok"))
        self.assertIn(
            pages[0].get("status"),
            {"LOG_CORRUPT", "ACK_JOURNAL_UNREADABLE", "ACK_JOURNAL_CORRUPT"},
        )
        self.assertEqual(path.read_bytes(), bad_bytes, "Corrupt bytes must be preserved")

    def test_b10_concurrent_publication_no_duplicate_layers(self):
        """B10: Concurrent publication produces no duplicate canonical layers."""
        finding = self.finding("concurrent body", finding_id="PAL-CONC")
        results = []

        def worker():
            r = self.publish(finding)
            results.append(r)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertTrue(r.get("ok"), r)

        layers = list((self.root / "audit").glob("*.md"))
        self.assertEqual(len(layers), 1, "Only one canonical layer file should be created")


if __name__ == "__main__":
    unittest.main()
