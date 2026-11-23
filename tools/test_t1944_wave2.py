"""SRC-343 wave-2 (audit/27.md) W2-001..W2-006 regressions.

Every class reproduces one measured defect against the real engine, using a
throwaway project. The reproductions are adversarial on purpose: a caller who
can shape the history, the cursor or a delivery result must not be able to turn
a lost record into a reported success.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from saipen_engine import audit_enqueue, campaign  # noqa: E402

# T-1947: the producer-specific backend lives outside the neutral engine.
from producer_backends import saipal_adapter  # noqa: E402


def _project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="t1944-w2-"))
    (root / ".saipen" / "campaign").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n## TODO\n## BLOCKED\n## DONE\n", encoding="utf-8"
    )
    return root


def _qualification(root: Path, receipt_id: str) -> dict:
    rel = f".saipen/campaign/qualifications/{receipt_id}.json"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"receipt_id": receipt_id, "state": "QUALIFIED"}), encoding="utf-8"
    )
    return {
        "receipt_id": receipt_id,
        "artifact_path": rel,
        "qualification_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _finding(root: Path, finding_id: str, **extra) -> dict:
    body = f"# Audit Finding {finding_id}\nbody\n"
    return {
        "finding_id": finding_id,
        "state": "QUALIFIED",
        "qualification_receipt": _qualification(root, f"QUAL-{finding_id}"),
        "audit_body": body,
        "artifact_digest": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        **extra,
    }


def _history_rows(root: Path, name: str) -> list:
    log = saipal_adapter._read_append_log(root / ".saipen" / "campaign" / name)
    return log.get("records") or []


class W2_001ReconcileIsOneTransaction(unittest.TestCase):
    """W2-001: a stale pre-lock LOG_ABSENT snapshot overwrote a newer log."""

    def setUp(self) -> None:
        self.root = _project()
        self.adapter = saipal_adapter.SaipalAdapter()

    def _enqueue(self, finding_id: str) -> dict:
        body = f"# {finding_id}\n"
        return audit_enqueue.enqueue(
            self.root,
            producer="saipal",
            body=body,
            producer_operation_id=f"saipal-{finding_id.lower()}",
            producer_item_id=finding_id,
        )

    def test_reconstruction_preserves_a_concurrently_created_log(self) -> None:
        """An append that lands before reconciliation reads must survive it.

        The old code decided `LOG_ABSENT` from an unlocked snapshot, rebuilt the
        log from the allocator and atomically replaced it, so a legitimate
        receipt appended between the read and the replace was silently erased.
        Under the fix the observation and the replacement share one lock, so the
        append either lands first (and is preserved) or waits. This exercises
        the "lands first" half at the exact point the stale snapshot used to be
        taken.
        """
        self._enqueue("PAL-RACE")
        concurrent = {
            "finding_id": "PAL-CONCURRENT",
            "operation_id": "saipal-pal-concurrent",
            "layer": 99,
            "digest": "0" * 64,
            "idempotent": False,
            "delivered_at": "2026-01-01T00:00:00Z",
        }
        appended = saipal_adapter._append_history_unique(
            self.root, "saipal_receipts.jsonl", concurrent
        )
        self.assertTrue(appended["ok"], appended)
        result = self.adapter.reconcile_history(
            self.root, kind="publication_receipts"
        )
        self.assertTrue(result["ok"], result)
        rows = _history_rows(self.root, "saipal_receipts.jsonl")
        operation_ids = {row.get("operation_id") for row in rows}
        self.assertIn("saipal-pal-concurrent", operation_ids)

    def test_the_whole_rebuild_holds_the_history_lock(self) -> None:
        """Lock exclusion, measured from inside the reconstruction itself.

        The lock has to cover the read, the rebuild and the replace. If it only
        covered the write, the stale-snapshot race would still exist, so this
        asks for the lock from inside the rebuild and requires it to be busy.
        """
        self._enqueue("PAL-LOCKED")
        log = self.root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('{"partial": ', encoding="utf-8")
        original = saipal_adapter._receipt_from_allocator
        observed = {}

        def probing_rebuild(root, row, **kwargs):
            probe = saipal_adapter.lock.FileWriterLock(
                root / ".saipen" / "locks" / "saipal-history.lock",
                root,
                blocking=False,
            )
            try:
                probe.acquire()
            except saipal_adapter.lock.FileLockBusy:
                observed["busy"] = True
            else:
                observed["busy"] = False
                probe.release()
            return original(root, row, **kwargs)

        with mock.patch.object(
            saipal_adapter, "_receipt_from_allocator", side_effect=probing_rebuild
        ):
            result = self.adapter.reconcile_history(
                self.root, kind="publication_receipts"
            )
        self.assertEqual(observed.get("busy"), True, result)
        self.assertTrue(result["ok"], result)

    def test_a_refused_reconciliation_reports_busy_instead_of_overwriting(self) -> None:
        self._enqueue("PAL-BUSY")
        holder = saipal_adapter.lock.FileWriterLock(
            self.root / ".saipen" / "locks" / "saipal-history.lock",
            self.root,
            blocking=False,
        )
        holder.acquire()
        try:
            with mock.patch.object(
                saipal_adapter, "_history_lock_timeout", return_value=0.0
            ):
                result = self.adapter.reconcile_history(
                    self.root, kind="publication_receipts"
                )
        finally:
            holder.release()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "RECONCILE_BUSY")

    def test_a_healthy_log_is_left_alone(self) -> None:
        self._enqueue("PAL-OK")
        seeded = {
            "finding_id": "PAL-OK",
            "operation_id": "saipal-pal-ok",
            "layer": 1,
            "digest": "0" * 64,
            "idempotent": False,
            "delivered_at": "2026-01-01T00:00:00Z",
        }
        appended = saipal_adapter._append_history_unique(
            self.root, "saipal_receipts.jsonl", seeded
        )
        self.assertTrue(appended["ok"], appended)
        before = (
            self.root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
        ).read_bytes()
        result = self.adapter.reconcile_history(self.root, kind="publication_receipts")
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["repaired"])
        self.assertEqual(
            (self.root / ".saipen" / "campaign" / "saipal_receipts.jsonl").read_bytes(),
            before,
        )



class W2_002YieldingIsNotDelivery(unittest.TestCase):
    """W2-002: the cursor acknowledged findings that were never published."""

    def setUp(self) -> None:
        self.root = _project()
        self.adapter = saipal_adapter.SaipalAdapter(saipal_home=self.root)
        payload = {
            "schema_version": 1,
            "ok": True,
            "command": "report",
            "findings": [
                {"finding_id": "PAL-1", "state": "QUALIFIED"},
            ],
            "counts": {"total": 1},
        }
        body = json.dumps(payload).encode("utf-8")
        # PERF-004 pages over the validated spool rather than a command result.
        self.adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": io.BytesIO(body),
            "stdout_bytes_len": len(body),
            "stderr": b"",
        }

    def test_a_yielded_but_unpublished_finding_stays_eligible(self) -> None:
        first = [page for page in self.adapter.iter_new_qualified_findings(self.root)]
        self.assertEqual(
            [row["finding_id"] for row in first[0]["findings"]], ["PAL-1"]
        )
        second = list(self.adapter.iter_new_qualified_findings(self.root))
        self.assertEqual(
            [row["finding_id"] for row in second[0]["findings"]],
            ["PAL-1"],
            "an unacknowledged finding must not disappear from the resumable set",
        )

    def test_acknowledgment_after_commit_suppresses_the_replay(self) -> None:
        page = next(self.adapter.iter_new_qualified_findings(self.root))
        digest = page["source_identity"]["source_digest"]
        ack = self.adapter.acknowledge_delivery(
            self.root, ["PAL-1"], source_digest=digest
        )
        self.assertTrue(ack["ok"], ack)
        after = next(self.adapter.iter_new_qualified_findings(self.root))
        self.assertEqual(after["findings"], [])

    def test_a_committed_allocator_operation_is_an_acknowledgment(self) -> None:
        """The allocator is the durable truth, not the cursor file."""
        body = "# PAL-1\nbody\n"
        audit_enqueue.enqueue(
            self.root,
            producer="saipal",
            body=body,
            producer_operation_id="saipal-pal-1",
            producer_item_id="PAL-1",
        )
        page = next(self.adapter.iter_new_qualified_findings(self.root))
        self.assertEqual(page["findings"], [])

    def test_a_refused_publication_keeps_the_finding_eligible(self) -> None:
        page = next(self.adapter.iter_new_qualified_findings(self.root))
        finding = {
            "finding_id": "PAL-1",
            "state": "QUALIFIED",
            "qualification_receipt": _qualification(self.root, "QUAL-PAL-1"),
            "audit_body": "# PAL-1\nbody\n",
            "artifact_digest": "deadbeef" * 8,
        }
        refused = self.adapter.deliver_finding_to_audit_inbox(
            self.root, finding, publication_authorized=True
        )
        self.assertFalse(refused["ok"])
        again = next(self.adapter.iter_new_qualified_findings(self.root))
        self.assertEqual(page["findings"][0]["finding_id"], "PAL-1")
        self.assertEqual([row["finding_id"] for row in again["findings"]], ["PAL-1"])


class W2_003ReceiptDeduplicationIsAtomic(unittest.TestCase):
    """W2-003: two identical concurrent deliveries appended two receipts."""

    def setUp(self) -> None:
        self.root = _project()
        self.finding = _finding(_project(), "PAL-777")

    def _deliver(self) -> dict:
        # The finding's qualification artifact lives in its own scratch project,
        # so materialise the same relative path inside the real root.
        rel = self.finding["qualification_receipt"]["artifact_path"]
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        source = Path(self.finding["qualification_receipt"]["materialized"])
        target.write_bytes(Path(source).read_bytes())
        return saipal_adapter.SaipalAdapter(saipal_home=self.root).deliver_finding_to_audit_inbox(
            self.root, self.finding, publication_authorized=True
        )

    def _prepare(self) -> None:
        scratch = Path(tempfile.mkdtemp(prefix="t1944-qual-"))
        rel = self.finding["qualification_receipt"]["artifact_path"]
        path = scratch / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"receipt_id": "QUAL-PAL-777", "state": "QUALIFIED"}),
            encoding="utf-8",
        )
        self.finding["qualification_receipt"] = {
            "receipt_id": "QUAL-PAL-777",
            "artifact_path": rel,
            "qualification_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
            "materialized": str(path),
        }

    def test_two_concurrent_lookups_cannot_both_see_absent(self) -> None:
        """W2-003: uniqueness has to be decided under the writer lock.

        The enqueue allocator already serialises publication, so two threads
        racing the public API usually observe each other's receipt by luck and
        the defect stays hidden. The defect is the GAP between the receipt
        lookup and the append, so this holds the lookup open: whichever thread
        reads the history first waits for a second reader.

        Pre-fix both readers run outside the lock, both conclude "absent" and
        both append, leaving two rows for one operation. Post-fix the second
        reader is still blocked on the writer lock, the wait expires, and the
        single surviving row is returned as a replay.
        """
        self._prepare()
        start = threading.Barrier(2, timeout=5.0)
        readers = threading.Barrier(2, timeout=0.75)
        original_read = saipal_adapter._read_append_log
        guard = threading.Lock()
        count = {"n": 0}

        def read_hook(path):
            with guard:
                count["n"] += 1
                ordinal = count["n"]
            if ordinal <= 2:
                with __import__("contextlib").suppress(threading.BrokenBarrierError):
                    readers.wait()
            return original_read(path)

        def go():
            start.wait()
            return self._deliver()

        with mock.patch.object(
            saipal_adapter, "_read_append_log", side_effect=read_hook
        ), __import__("concurrent.futures").futures.ThreadPoolExecutor(
            max_workers=2
        ) as pool:
            results = list(pool.map(lambda _: go(), range(2)))
        self.assertTrue(any(row.get("ok") for row in results), results)
        rows = _history_rows(self.root, "saipal_receipts.jsonl")
        self.assertEqual(
            len(rows), 1, f"one operation must have one receipt, got {len(rows)}"
        )
        self.assertEqual(rows[0]["operation_id"], "saipal-pal-777")

    def test_ten_simultaneous_deliveries_leave_one_receipt(self) -> None:
        self._prepare()
        barrier = threading.Barrier(10)

        def go():
            barrier.wait()
            return self._deliver()

        with __import__("concurrent.futures").futures.ThreadPoolExecutor(
            max_workers=10
        ) as pool:
            results = list(pool.map(lambda _: go(), range(10)))
        self.assertTrue(any(row.get("ok") for row in results), results)
        rows = _history_rows(self.root, "saipal_receipts.jsonl")
        self.assertEqual(
            len(rows), 1, f"one operation must have one receipt, got {len(rows)}"
        )
        self.assertEqual(rows[0]["operation_id"], "saipal-pal-777")

    def test_a_conflicting_digest_is_refused_not_overwritten(self) -> None:
        self._prepare()
        first = self._deliver()
        self.assertTrue(first["ok"], first)
        stored = _history_rows(self.root, "saipal_receipts.jsonl")[0]
        record = dict(stored)
        record["digest"] = "f" * 64
        outcome = saipal_adapter._append_history_unique(
            self.root, "saipal_receipts.jsonl", record
        )
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["status"], "HISTORY_CONFLICT")

    def test_an_identical_row_is_returned_with_its_original_timestamp(self) -> None:
        self._prepare()
        first = self._deliver()
        original = _history_rows(self.root, "saipal_receipts.jsonl")[0]
        repeat = self._deliver()
        self.assertTrue(repeat["ok"], repeat)
        self.assertTrue(repeat.get("idempotent_replay"))
        self.assertEqual(
            _history_rows(self.root, "saipal_receipts.jsonl")[0]["delivered_at"],
            original["delivered_at"],
        )
        self.assertEqual(first["receipt"]["operation_id"], "saipal-pal-777")


class W2_004DeliveryAggregateIsTruthful(unittest.TestCase):
    """W2-004: a failed batch was reported as DISCOVERY_DELIVERED."""

    def setUp(self) -> None:
        self.root = _project()

    def _controller_with(self, delivery: dict, findings: list | None = None):
        ctrl = campaign.CampaignController(self.root)
        ctrl.backend = mock.Mock()
        ctrl.backend.discover.return_value = {
            "ok": True,
            "status": saipal_adapter.NEW_QUALIFIED_FINDINGS,
            "findings": findings if findings is not None else [{"finding_id": "PAL-1"}],
        }
        ctrl.backend.deliver_finding_to_audit_inbox.return_value = delivery
        return ctrl

    def _admit(self, ctrl) -> None:
        campaign.save_campaign_state(
            self.root,
            {
                "schema_version": campaign.CAMPAIGN_SCHEMA_VERSION,
                "campaign_id": "CAMP-W2-004",
                "campaign_state": campaign.ADMITTED,
                "authority_proof_reference": ".saipen/authority/grant.json",
            },
        )

    def _maintenance_step(self, ctrl) -> dict:
        """Drive `step()` down the MAINTENANCE_AVAILABLE -> discovery branch."""
        assessment = {
            "classification": campaign.ca.MAINTENANCE_AVAILABLE,
            "next_action": "forensic_discovery",
        }
        with mock.patch.object(
            campaign.ca, "assess_continuation", return_value=assessment
        ), mock.patch.object(
            campaign, "_verify_state_grant", return_value={"valid": True}
        ):
            return ctrl.step(worker_func=lambda r, g: {"progress_verified": True})

    def test_every_failed_delivery_never_reports_delivered(self) -> None:
        ctrl = self._controller_with(
            {"ok": False, "status": "ARTIFACT_MISSING", "finding_id": "PAL-1"}
        )
        self._admit(ctrl)
        outcome = self._maintenance_step(ctrl)
        self.assertFalse(outcome.get("ok"), outcome)
        self.assertEqual(outcome.get("event"), "DISCOVERY_DELIVERY_FAILED")
        self.assertEqual(outcome["delivery_status"], "NONE_DELIVERED")

    def test_a_staged_finding_is_not_a_publication(self) -> None:
        ctrl = self._controller_with(
            {"ok": False, "status": saipal_adapter.STAGED_PUBLICATION}
        )
        self._admit(ctrl)
        outcome = self._maintenance_step(ctrl)
        self.assertFalse(outcome.get("ok"), outcome)
        self.assertEqual(outcome["delivery_status"], "PUBLICATION_STAGED")

    def test_a_mixed_batch_names_both_sides_exactly(self) -> None:
        ctrl = campaign.CampaignController(self.root)
        ctrl.backend = mock.Mock()
        ctrl.backend.discover.return_value = {
            "ok": True,
            "status": saipal_adapter.NEW_QUALIFIED_FINDINGS,
            "findings": [{"finding_id": "PAL-OK"}, {"finding_id": "PAL-BAD"}],
        }
        ctrl.backend.deliver_finding_to_audit_inbox.side_effect = [
            {"ok": True, "status": saipal_adapter.DELIVERED_PUBLICATION, "finding_id": "PAL-OK"},
            {"ok": False, "status": "ARTIFACT_MISSING", "finding_id": "PAL-BAD"},
        ]
        self._admit(ctrl)
        outcome = self._maintenance_step(ctrl)
        self.assertTrue(outcome.get("ok"), outcome)
        self.assertEqual(outcome["delivery_status"], "PARTIALLY_DELIVERED")
        self.assertEqual(outcome["published_finding_ids"], ["PAL-OK"])
        self.assertEqual(outcome["failed_finding_ids"], ["PAL-BAD"])

    def test_an_unknown_outcome_requires_reconciliation(self) -> None:
        ctrl = self._controller_with(
            {
                "ok": False,
                "status": "HISTORY_WRITE_FAILED",
                "receipt_reconciliation_required": True,
                "enqueue_committed": True,
            }
        )
        self._admit(ctrl)
        outcome = self._maintenance_step(ctrl)
        self.assertFalse(outcome.get("ok"), outcome)
        self.assertEqual(outcome["delivery_status"], "PUBLICATION_OUTCOME_UNKNOWN")

    def test_a_full_success_still_reports_delivery(self) -> None:
        ctrl = self._controller_with(
            {"ok": True, "status": saipal_adapter.DELIVERED_PUBLICATION, "finding_id": "PAL-1"}
        )
        self._admit(ctrl)
        outcome = self._maintenance_step(ctrl)
        self.assertTrue(outcome.get("ok"), outcome)
        self.assertEqual(outcome["event"], "DISCOVERY_DELIVERED")
        self.assertEqual(outcome["delivery_status"], "ALL_DELIVERED")


class W2_005CursorIntegrityIsNeverIgnored(unittest.TestCase):
    """W2-005: a corrupt cursor was replaced and a failed write was swallowed."""

    def setUp(self) -> None:
        self.root = _project()
        self.adapter = saipal_adapter.SaipalAdapter(saipal_home=self.root)
        payload = {
            "schema_version": 1,
            "ok": True,
            "command": "report",
            "findings": [{"finding_id": "PAL-1", "state": "QUALIFIED"}],
            "counts": {"total": 1},
        }
        body = json.dumps(payload).encode("utf-8")
        self.adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": io.BytesIO(body),
            "stdout_bytes_len": len(body),
            "stderr": b"",
        }
        self.cursor = self.root / ".saipen" / "campaign" / "saipal_report_cursor.json"

    def test_a_corrupt_cursor_is_refused_and_preserved(self) -> None:
        self.cursor.write_text("{incomplete-original-cursor", encoding="utf-8")
        before = self.cursor.read_bytes()
        pages = list(self.adapter.iter_new_qualified_findings(self.root))
        self.assertEqual(len(pages), 1)
        self.assertFalse(pages[0]["ok"])
        self.assertEqual(pages[0]["status"], "CURSOR_CORRUPT")
        self.assertEqual(self.cursor.read_bytes(), before)
        self.assertFalse(self.adapter.load_page_checkpoint(self.root)["ok"])

    def test_a_failed_cursor_write_is_surfaced(self) -> None:
        with mock.patch.object(
            self.adapter,
            "save_page_checkpoint",
            return_value={"ok": False, "status": "CURSOR_WRITE_FAILED", "error": "disk full"},
        ):
            pages = list(self.adapter.iter_new_qualified_findings(self.root))
        self.assertEqual(len(pages), 1)
        self.assertFalse(pages[0]["ok"])
        self.assertEqual(pages[0]["status"], "CURSOR_WRITE_FAILED")
        self.assertFalse(pages[0]["persisted"])

    def test_a_missing_cursor_is_an_ordinary_initial_state(self) -> None:
        self.assertFalse(self.cursor.exists())
        pages = list(self.adapter.iter_new_qualified_findings(self.root))
        self.assertTrue(pages[0]["ok"], pages[0])

    def test_a_valid_cursor_is_accepted(self) -> None:
        self.adapter.save_page_checkpoint(
            self.root, {"source_digest": "x", "delivered_finding_ids": []}
        )
        loaded = self.adapter.load_page_checkpoint(self.root)
        self.assertTrue(loaded["ok"])
        self.assertEqual(loaded["status"], "CURSOR_OK")


class W2_006CorpusIdentityCoversContent(unittest.TestCase):
    """W2-006: finding ids stood in for finding content, so edits were invisible."""

    def _digest(self, findings: list) -> str:
        adapter = saipal_adapter.SaipalAdapter(saipal_home=".")
        body = json.dumps(
            {
                "schema_version": 1,
                "ok": True,
                "command": "report",
                "findings": findings,
                "counts": {},
            }
        ).encode("utf-8")
        adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": io.BytesIO(body),
            "stdout_bytes_len": len(body),
            "stderr": b"",
        }
        return next(iter(adapter.iter_finding_pages(page_size=100)))[3]["source_digest"]

    def test_identical_reports_share_one_identity(self) -> None:
        rows = [{"finding_id": "PAL-1", "state": "QUALIFIED"}]
        self.assertEqual(self._digest(rows), self._digest(list(rows)))

    def test_changing_audit_body_changes_identity(self) -> None:
        a = [{"finding_id": "PAL-1", "state": "QUALIFIED", "audit_body": "# one\n"}]
        b = [{"finding_id": "PAL-1", "state": "QUALIFIED", "audit_body": "# two\n"}]
        self.assertNotEqual(self._digest(a), self._digest(b))

    def test_changing_qualification_evidence_changes_identity(self) -> None:
        a = [{"finding_id": "PAL-1", "state": "QUALIFIED", "qualification_digest": "a" * 64}]
        b = [{"finding_id": "PAL-1", "state": "QUALIFIED", "qualification_digest": "b" * 64}]
        self.assertNotEqual(self._digest(a), self._digest(b))

    def test_adding_and_removing_findings_changes_identity(self) -> None:
        one = [{"finding_id": "PAL-1", "state": "QUALIFIED"}]
        two = [*one, {"finding_id": "PAL-2", "state": "QUALIFIED"}]
        self.assertNotEqual(self._digest(one), self._digest(two))
        self.assertNotEqual(self._digest(two), self._digest(one))

    def test_a_changed_state_changes_identity(self) -> None:
        a = [{"finding_id": "PAL-1", "state": "QUALIFIED"}]
        b = [{"finding_id": "PAL-1", "state": "CONFIRMED"}]
        self.assertNotEqual(self._digest(a), self._digest(b))


if __name__ == "__main__":
    unittest.main()
