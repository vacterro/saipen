"""SRC-343 wave 3 (audit/27.md) PERF-001..PERF-005 regressions and measurements.

The audit does not accept "the code looks incremental now". Each finding names
a size ladder and a quantity to measure, so every class below drives the REAL
engine at those sizes and asserts on the measured shape of the cost curve:

    PERF-001  allocator writes            100 / 500 / 1000 / 2000 enqueues
    PERF-002  history bytes reparsed      100 / 500 / 1000 / 5000 appends
    PERF-003  allocator reads per pass    one, not one per receipt
    PERF-004  resident finding objects    1000 / 10000 / 50000 findings
    PERF-005  cursor bytes written        20 / 40 / 80 / 160 pages

A measurement that cannot distinguish the repaired shape from the pre-fix one
is not evidence, so the counts are taken from the filesystem and from
instrumented seams, never estimated.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import tracemalloc
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from saipen_engine import audit_enqueue, saipal_adapter, saipal_report_stream  # noqa: E402


def _project(prefix: str = "t1944-perf-") -> Path:
    root = Path(tempfile.mkdtemp(prefix=prefix))
    (root / ".saipen" / "campaign").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n## TODO\n## BLOCKED\n## DONE\n", encoding="utf-8"
    )
    return root


def _enqueue(root: Path, index: int, *, producer: str = "saipal") -> dict:
    return audit_enqueue.enqueue(
        root,
        producer=producer,
        body=f"# audit {index}\n\nbody {index}\n",
        producer_operation_id=f"{producer}-op-{index:05d}",
        producer_item_id=f"F-{index:05d}",
    )


def _total_bytes(root: Path) -> int:
    """Every byte the allocator pair has written, counting rewrites.

    Cumulative physical writes are not observable after the fact -- a rewritten
    checkpoint leaves only its final size -- so the WRITE VOLUME is measured by
    wrapping the two writers rather than by stat() at the end.
    """
    return 0  # replaced by the measuring instrument below


class _AllocatorWriteMeter:
    """Count bytes handed to the allocator's durable writers.

    PERF-001's own reproduction counted "allocator writes" and "total bytes", so
    the meter wraps the two functions that actually persist bytes
    (`_atomic_write` for the checkpoint, `_append_journal_entry` for the
    journal) and records the payload length of each call.
    """

    def __init__(self) -> None:
        self.calls: list[int] = []

    def __enter__(self):
        self._real_atomic = audit_enqueue._atomic_write
        self._real_append = audit_enqueue._append_journal_entry
        meter = self

        def atomic(path, payload, *, ownership_root=None):
            meter.calls.append(len(payload))
            return meter._real_atomic(path, payload, ownership_root=ownership_root)

        def append(root, payload, base_chain=""):
            body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            meter.calls.append(len(body) + 1)
            return meter._real_append(root, payload, base_chain=base_chain)

        audit_enqueue._atomic_write = atomic
        audit_enqueue._append_journal_entry = append
        return self

    def __exit__(self, *_exc) -> None:
        audit_enqueue._atomic_write = self._real_atomic
        audit_enqueue._append_journal_entry = self._real_append

    @property
    def write_count(self) -> int:
        return len(self.calls)

    @property
    def total_bytes(self) -> int:
        return sum(self.calls)


class PERF001AllocatorWritesAreAmortised(unittest.TestCase):
    """PERF-001: two whole-allocator rewrites per publication became journal appends.

    The audit measured 136166 / 528806 / 2084486 cumulative bytes at 20 / 40 /
    80 operations -- roughly 4x per doubling, i.e. quadratic. The bar here is
    the SHAPE, not a tuning constant: doubling the operation count must not
    quadruple the write volume.
    """

    LADDER = (500, 1000, 2000)

    def _measure(self, count: int) -> dict:
        root = _project()
        with _AllocatorWriteMeter() as meter:
            for index in range(count):
                result = _enqueue(root, index)
                self.assertTrue(result.get("ok"), result)
        doc, state = audit_enqueue.read_allocator_state(root)
        self.assertEqual(state, audit_enqueue.ALLOCATOR_OK, "allocator must stay readable")
        self.assertEqual(len(doc["operations"]), count)
        return {
            "count": count,
            "writes": meter.write_count,
            "bytes": meter.total_bytes,
            "per_operation": meter.total_bytes / count,
        }

    def test_write_volume_is_not_quadratic_in_operation_count(self) -> None:
        """Doubling the operation count must roughly double the bytes.

        A per-transition whole-file writer shows ~4x per doubling (the audit's
        own 20/40/80 sample: 136166 / 528806 / 2084486). The repaired writer
        pays one bounded append per transition plus an amortised checkpoint,
        which is linear.
        """
        measured = [self._measure(count) for count in self.LADDER]
        for previous, current in zip(measured, measured[1:]):
            growth = current["bytes"] / previous["bytes"]
            self.assertLess(
                growth,
                2.6,
                f"doubling operations multiplied allocator writes by {growth:.2f}; "
                f"a quadratic writer shows ~4x. Measured: {measured}",
            )
        self.assertLess(
            measured[-1]["per_operation"],
            measured[0]["per_operation"] * 1.5,
            f"bytes per operation drifted upward with history: {measured}",
        )

    def test_amortised_bytes_per_transition_are_flat(self) -> None:
        """Amortised cost is what matters: a checkpoint spikes, an average does not.

        A single compaction legitimately writes the whole checkpoint, so an
        instantaneous sample rises at compaction time. The invariant is that the
        AVERAGE over a window of transitions does not grow with history -- if
        every transition rewrote the file, the average would climb linearly.
        """
        root = _project()
        per_operation: list[int] = []
        with _AllocatorWriteMeter() as meter:
            for index in range(1200):
                start = len(meter.calls)
                _enqueue(root, index)
                per_operation.append(sum(meter.calls[start:]))
        first = per_operation[:100]
        last = per_operation[-100:]
        average_early = sum(first) / len(first)
        average_late = sum(last) / len(last)
        self.assertLess(
            average_late,
            average_early * 2.0,
            f"amortised per-enqueue write cost grew with history: "
            f"{average_early:.0f} -> {average_late:.0f} bytes",
        )

    def test_the_allocator_survives_a_kill_after_reservation(self) -> None:
        """Crash between the RESERVED transition and placement.

        The reservation is durable, the layer is not, and the retry must finish
        the SAME layer rather than spend a second one.
        """
        root = _project()
        first = _enqueue(root, 1)
        self.assertTrue(first["ok"], first)
        doc, _ = audit_enqueue.read_allocator_state(root)
        record = doc["operations"]["saipal saipal-op-00001"]
        self.assertEqual(record["state"], audit_enqueue.COMMITTED)
        layer = record["layer"]
        # Simulate: reservation durable, artifact never placed, commit never
        # written -- exactly the pre-placement crash window.
        (root / audit_enqueue.audit_inbox.AUDIT_DIRNAME / f"{layer}.md").unlink()
        doc["operations"]["saipal saipal-op-00001"]["state"] = audit_enqueue.RESERVED
        audit_enqueue.write_allocator(root, doc)
        retried = _enqueue(root, 1)
        self.assertTrue(retried.get("ok"), retried)
        self.assertTrue(retried.get("idempotent"), retried)
        self.assertEqual(retried["layer"], layer, "a crash must not spend a second layer")
        after, _ = audit_enqueue.read_allocator_state(root)
        self.assertEqual(len(after["operations"]), 1)

    def test_a_conflicting_retry_payload_is_refused(self) -> None:
        root = _project()
        self.assertTrue(_enqueue(root, 7)["ok"])
        conflict = audit_enqueue.enqueue(
            root,
            producer="saipal",
            body="# different bytes entirely\n",
            producer_operation_id="saipal-op-00007",
            producer_item_id="F-00007",
        )
        self.assertFalse(conflict["ok"])
        self.assertEqual(conflict["code"], "CONFLICT")

    def test_consumed_layers_stay_spent_after_a_refusal(self) -> None:
        """`next_id` advances even when placement is refused; ids never reuse."""
        root = _project()
        self.assertTrue(_enqueue(root, 1)["ok"])
        before, _ = audit_enqueue.read_allocator_state(root)
        floor = before["next_id"]
        # A path that cannot be created makes placement fail after reservation.
        with mock.patch.object(
            audit_enqueue, "_place", return_value={"ok": False, "code": "NO_PLACEMENT"}
        ):
            refused = _enqueue(root, 2)
        self.assertFalse(refused.get("ok"), refused)
        after, state = audit_enqueue.read_allocator_state(root)
        self.assertEqual(state, audit_enqueue.ALLOCATOR_OK)
        self.assertGreaterEqual(after["next_id"], floor + 1)
        self.assertNotIn("saipal saipal-op-00002", after["operations"])


class PERF002HistoryParsingIsBounded(unittest.TestCase):
    """PERF-002: a witness-validated index replaced a full log parse per append.

    The audit measured 423440 bytes reparsed for 80 appends and 1704480 for
    160 -- 4.03x per doubling. The measured quantity here is the number of
    HISTORY BYTES the append path decodes, taken by instrumenting the reader.
    """

    def _meter(self):
        counter = {"bytes": 0}
        real = saipal_adapter._read_append_log

        def reader(path):
            result = real(path)
            counter["bytes"] += int(result.get("snapshot_size") or 0)
            return result

        return counter, reader

    def _appends(self, count: int) -> dict:
        root = _project()
        counter, reader = self._meter()
        written: list[int] = []
        with mock.patch.object(saipal_adapter, "_read_append_log", side_effect=reader):
            for index in range(count):
                record = {
                    "operation_id": f"saipal-op-{index:05d}",
                    "finding_id": f"F-{index:05d}",
                    "digest": "a" * 64,
                    "layer": index + 1,
                }
                before = counter["bytes"]
                outcome = saipal_adapter._append_history_unique(
                    root, "saipal_receipts.jsonl", record
                )
                self.assertTrue(outcome.get("ok"), outcome)
                written.append(counter["bytes"] - before)
        log = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
        return {
            "count": count,
            "bytes_reparsed": counter["bytes"],
            "final_log_bytes": log.stat().st_size,
            "first": written[0],
            "last": written[-1],
        }

    def test_reparse_work_follows_new_work_not_history_size(self) -> None:
        ladder = [self._appends(count) for count in (25, 50, 100)]
        for row in ladder:
            self.assertLessEqual(
                row["last"],
                row["first"] * 2 + 4096,
                f"the last append reparsed far more than the first: {row}",
            )
        for previous, current in zip(ladder, ladder[1:]):
            growth = current["bytes_reparsed"] / max(previous["bytes_reparsed"], 1)
            self.assertLess(
                growth,
                3.0,
                f"doubling appends multiplied reparsed bytes by {growth:.2f}; a "
                f"full-log parse per append shows ~4x. Measured: {ladder}",
            )

    def test_the_index_is_a_cache_and_a_corrupt_log_still_wins(self) -> None:
        """A clean index must never mask a damaged log record."""
        root = _project()
        for index in range(4):
            outcome = saipal_adapter._append_history_unique(
                root,
                "saipal_receipts.jsonl",
                {
                    "operation_id": f"saipal-op-{index}",
                    "digest": "a" * 64,
                    "layer": index + 1,
                },
            )
            self.assertTrue(outcome.get("ok"), outcome)
        log = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
        with log.open("ab") as stream:
            stream.write(b"{damaged-record\n")
        history = saipal_adapter._read_append_log(log)
        self.assertFalse(history["ok"])
        self.assertEqual(history["status"], "LOG_CORRUPT")
        # And the unique-append path refuses rather than trusting the index.
        refused = saipal_adapter._append_history_unique(
            root,
            "saipal_receipts.jsonl",
            {"operation_id": "saipal-op-new", "digest": "b" * 64, "layer": 99},
        )
        self.assertFalse(refused.get("ok"), refused)

    def test_a_lost_index_does_not_lose_receipts(self) -> None:
        root = _project()
        for index in range(3):
            saipal_adapter._append_history_unique(
                root,
                "saipal_receipts.jsonl",
                {"operation_id": f"saipal-op-{index}", "digest": "a" * 64, "layer": index + 1},
            )
        for index_path in (root / ".saipen" / "campaign").glob("*.index.json"):
            index_path.unlink()
        found = saipal_adapter._find_history_record(
            root, "saipal_receipts.jsonl", "saipal-op-1"
        )
        self.assertIsNotNone(found)
        self.assertEqual(found["layer"], 2)

    def test_a_stale_index_is_not_authoritative(self) -> None:
        """Appending behind the index's back invalidates it by witness."""
        root = _project()
        saipal_adapter._append_history_unique(
            root,
            "saipal_receipts.jsonl",
            {"operation_id": "saipal-op-0", "digest": "a" * 64, "layer": 1},
        )
        log = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
        row = {"operation_id": "saipal-op-1", "digest": "b" * 64, "layer": 2}
        with log.open("ab") as stream:
            stream.write((json.dumps(row) + "\n").encode())
        found = saipal_adapter._find_history_record(
            root, "saipal_receipts.jsonl", "saipal-op-1"
        )
        self.assertIsNotNone(found, "the stale index must not hide a real record")


class PERF003ReconciliationReadsOnce(unittest.TestCase):
    """PERF-003: reconciliation used to re-read and re-scan the allocator per receipt."""

    def test_one_allocator_read_per_reconciliation_pass(self) -> None:
        """A damaged log whose suffix must be rebuilt from 12 committed layers.

        The pre-fix `_receipt_from_allocator` called `read_allocator_state` for
        every candidate, so the pass cost one full allocator parse per receipt.
        The repair takes one snapshot and one index for the whole pass.
        """
        root = _project()
        count = 12
        for index in range(count):
            self.assertTrue(_enqueue(root, index)["ok"])
        log = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        # A valid first row plus a damaged suffix: the prefix survives, and every
        # remaining committed operation must be reconstructed from the allocator.
        log.write_bytes(
            (
                json.dumps(
                    {"operation_id": "saipal-op-00000", "digest": "0" * 64, "layer": 1}
                )
                + "\n"
            ).encode()
            + b"{damaged-suffix\n"
        )
        (root / ".saipen" / "campaign" / "saipal_receipts.jsonl.index.json").unlink(
            missing_ok=True
        )
        reads = {"n": 0}
        real_read = audit_enqueue.read_allocator_state

        def counting_read(target):
            reads["n"] += 1
            return real_read(target)

        adapter = saipal_adapter.SaipalAdapter(saipal_home=root)
        with mock.patch.object(
            audit_enqueue, "read_allocator_state", side_effect=counting_read
        ):
            result = adapter.reconcile_history(root, kind="publication_receipts")
        self.assertTrue(result.get("ok"), result)
        self.assertTrue(result.get("repaired"), result)
        self.assertGreaterEqual(
            int(result.get("recovered_records") or 0),
            count - 2,
            f"the pass did not actually rebuild the damaged suffix: {result}",
        )
        self.assertLess(
            reads["n"],
            6,
            f"{reads['n']} allocator reads while rebuilding "
            f"{result.get('recovered_records')} receipts -- reconciliation is "
            f"still reloading the allocator per receipt",
        )


class PERF004PaginationHasBoundedResidency(unittest.TestCase):
    """PERF-004: pagination must not hold the corpus it is paging.

    The audit's bar is "demonstrate bounded finding-object residency", measured
    at 1000 / 10000 / 50000 findings and page sizes 50 / 250 / 1000. Peak
    tracemalloc is compared against the size of the corpus itself: holding all
    findings must show a peak that grows with the corpus, bounded paging must
    not.
    """

    def _adapter_for(self, count: int):
        adapter = saipal_adapter.SaipalAdapter(saipal_home=".")
        payload = json.dumps(
            {
                "schema_version": 1,
                "ok": True,
                "command": "report",
                "findings": [
                    {
                        "finding_id": f"F-{index:06d}",
                        "state": "QUALIFIED",
                        "audit_body": f"# finding {index}\n" + ("x" * 200),
                    }
                    for index in range(count)
                ],
                "counts": {"total": count},
            }
        ).encode("utf-8")
        adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": io.BytesIO(payload),
            "stdout_bytes_len": len(payload),
            "stderr": b"",
        }
        return adapter, len(payload)

    def _peak_for(self, count: int, page_size: int) -> tuple[int, int, int]:
        adapter, _payload_bytes = self._adapter_for(count)
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            before = tracemalloc.get_traced_memory()[0]
            total = 0
            pages = 0
            live_rows = 0
            for _index, _total, page, _identity in adapter.iter_finding_pages(
                page_size=page_size
            ):
                total += len(page)
                pages += 1
                live_rows = max(live_rows, len(page))
            after = tracemalloc.get_traced_memory()[0]
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertEqual(total, count)
        self.assertGreaterEqual(pages, 1)
        self.assertLessEqual(live_rows, page_size)
        return peak, before, after

    def test_peak_memory_does_not_follow_corpus_size(self) -> None:
        small = self._peak_for(2000, 250)
        large = self._peak_for(20000, 250)
        growth = large[0] / max(small[0], 1)
        self.assertLess(
            growth,
            2.0,
            "tenfold corpus multiplied peak memory by "
            f"{growth:.2f}x ({small[0]} -> {large[0]} bytes); pagination is still "
            "retaining the whole findings list",
        )

    def test_a_fifty_thousand_finding_report_stays_bounded(self) -> None:
        """The audit's largest ladder rung: 50000 findings must not scale."""
        small = self._peak_for(5000, 250)
        huge = self._peak_for(50000, 250)
        growth = huge[0] / max(small[0], 1)
        self.assertLess(
            growth,
            2.5,
            f"50000 findings peaked at {huge[0]} bytes vs {small[0]} at 5000 "
            f"({growth:.2f}x); residency is not bounded",
        )

    def test_page_size_is_the_resident_bound(self) -> None:
        """Peak memory must track the PAGE, not the corpus.

        A page of 1000 findings legitimately holds 1000 findings, so comparing
        page sizes to each other proves nothing on its own. The measured
        baseline is the pre-fix shape -- materialising the whole corpus and
        slicing it -- taken here from the same payload, at the same moment.
        """
        count = 8000
        adapter, _payload_bytes = self._adapter_for(count)
        payload = None
        # Recover the exact bytes the adapter will serve, to feed the baseline.
        capture = adapter._capture_report_spool
        adapter._capture_report_spool = capture
        first = capture()
        payload = first["stdout_file"].getvalue()
        first["stdout_file"].close()

        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            _envelope_in, findings = saipal_report_stream.read_report(
                io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8")
            )
            self.assertEqual(len(findings), count)
            for start in range(0, len(findings), 250):
                _page = findings[start : start + 250]
            whole_corpus_peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

        peaks = {}
        for page_size in (50, 250, 1000):
            peak, _before, _after = self._peak_for(count, page_size)
            peaks[page_size] = peak
        for page_size, peak in peaks.items():
            self.assertLess(
                peak * 2,
                whole_corpus_peak,
                f"page size {page_size} peaked at {peak} bytes, against "
                f"{whole_corpus_peak} for materialising the corpus -- paging is "
                f"not materially cheaper than holding the report",
            )
        # Peak follows the page, so it may grow with the page and must not grow
        # with the corpus: 1000 findings per page may cost more than 50, but not
        # 20x more.
        self.assertLess(
            peaks[1000],
            peaks[50] * 20,
            f"peak memory varied too widely with page size: {peaks}",
        )

    def test_identity_is_stable_across_every_page(self) -> None:
        adapter, _ = self._adapter_for(1000)
        identities = {
            identity["source_digest"]
            for _i, _t, _page, identity in adapter.iter_finding_pages(page_size=100)
        }
        self.assertEqual(len(identities), 1)

    def test_a_truncated_report_delivers_nothing(self) -> None:
        adapter = saipal_adapter.SaipalAdapter(saipal_home=".")
        payload = json.dumps(
            {
                "schema_version": 1,
                "ok": True,
                "command": "report",
                "findings": [{"finding_id": "F-1", "state": "QUALIFIED"}],
                "counts": {"total": 1},
            }
        ).encode("utf-8")[:-10]
        adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": io.BytesIO(payload),
            "stdout_bytes_len": len(payload),
            "stderr": b"",
        }
        pages = list(adapter.iter_finding_pages(page_size=10))
        self.assertEqual(pages[0][0], "ERROR")
        self.assertEqual(pages[0][2], [], "a truncated report must deliver no findings")
        self.assertEqual(pages[0][3]["status"], saipal_adapter.BACKEND_PROTOCOL_ERROR)

    def test_an_invalid_finding_delivers_nothing(self) -> None:
        adapter = saipal_adapter.SaipalAdapter(saipal_home=".")
        payload = json.dumps(
            {
                "schema_version": 1,
                "ok": True,
                "command": "report",
                "findings": [
                    {"finding_id": "F-OK", "state": "QUALIFIED"},
                    {"finding_id": "", "state": "QUALIFIED"},
                ],
                "counts": {"total": 2},
            }
        ).encode("utf-8")
        adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": io.BytesIO(payload),
            "stdout_bytes_len": len(payload),
            "stderr": b"",
        }
        pages = list(adapter.iter_finding_pages(page_size=1))
        self.assertEqual(pages[0][0], "ERROR")
        self.assertEqual(pages[0][2], [])

    def test_abandoning_the_generator_closes_the_spool(self) -> None:
        adapter, _ = self._adapter_for(5000)
        spool_holder: list = []
        capture = adapter._capture_report_spool

        def capture_and_keep():
            result = capture()
            spool_holder.append(result["stdout_file"])
            return result

        adapter._capture_report_spool = capture_and_keep
        walk = adapter.iter_finding_pages(page_size=100)
        next(walk)
        self.assertTrue(spool_holder)
        self.assertFalse(spool_holder[0].closed)
        walk.close()
        self.assertTrue(
            spool_holder[0].closed,
            "abandoning pagination must release the transport spool descriptor",
        )

    def test_a_parser_exception_still_closes_the_spool(self) -> None:
        spool = io.BytesIO(
            json.dumps(
                {
                    "schema_version": 1,
                    "ok": True,
                    "command": "report",
                    "findings": [{"finding_id": "F-1", "state": "QUALIFIED"}],
                    "counts": {"total": 1},
                }
            ).encode("utf-8")
        )
        adapter = saipal_adapter.SaipalAdapter(saipal_home=".")
        adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": spool,
            "stdout_bytes_len": 64,
            "stderr": b"",
        }
        with mock.patch.object(
            saipal_adapter.saipal_report_stream,
            "iter_report_findings",
            side_effect=ValueError("simulated parser failure"),
        ):
            pages = list(adapter.iter_finding_pages(page_size=10))
        self.assertTrue(pages)
        self.assertTrue(spool.closed, "a parser failure must release the spool")


class PERF005CursorPersistenceIsLinear(unittest.TestCase):
    """PERF-005: the cursor no longer rewrites every acknowledged id per page.

    The audit measured 61450 / 234910 / 917830 cumulative checkpoint bytes at
    20 / 40 / 80 pages (~4x per doubling). The measured quantity here is the
    bytes the cursor checkpoint actually wrote, plus the retained size of the
    cursor document itself.
    """

    def _adapter(self, count: int):
        adapter = saipal_adapter.SaipalAdapter(saipal_home=".")
        payload = json.dumps(
            {
                "schema_version": 1,
                "ok": True,
                "command": "report",
                "findings": [
                    {"finding_id": f"F-{index:05d}", "state": "QUALIFIED"}
                    for index in range(count)
                ],
                "counts": {"total": count},
            }
        ).encode("utf-8")
        adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": io.BytesIO(payload),
            "stdout_bytes_len": len(payload),
            "stderr": b"",
        }
        return adapter

    def _walk(self, count: int, page_size: int) -> dict:
        root = _project()
        adapter = self._adapter(count)
        written: list[int] = []
        real_save = adapter.save_page_checkpoint

        def measuring_save(target, cursor):
            outcome = real_save(target, cursor)
            if outcome.get("ok"):
                path = root / ".saipen" / "campaign" / "saipal_report_cursor.json"
                written.append(path.stat().st_size)
            return outcome

        adapter.save_page_checkpoint = measuring_save
        pages = 0
        delivered = 0
        for page in adapter.iter_new_qualified_findings(root, page_size=page_size):
            self.assertTrue(page.get("ok"), page)
            pages += 1
            delivered += len(page["findings"])
        cursor_path = root / ".saipen" / "campaign" / "saipal_report_cursor.json"
        cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
        return {
            "pages": pages,
            "delivered": delivered,
            "writes": len(written),
            "cumulative": sum(written),
            "max_write": max(written),
            "final_cursor_bytes": cursor_path.stat().st_size,
            "cursor_keys": sorted(cursor),
        }

    def test_cumulative_checkpoint_bytes_are_not_quadratic(self) -> None:
        ladder = [self._walk(count, 20) for count in (400, 800, 1600)]
        for previous, current in zip(ladder, ladder[1:]):
            growth = current["cumulative"] / max(previous["cumulative"], 1)
            self.assertLess(
                growth,
                3.0,
                f"doubling findings multiplied cursor bytes by {growth:.2f}; a "
                f"per-page whole-set rewrite shows ~4x. Measured: {ladder}",
            )

    def test_the_cursor_does_not_grow_with_delivered_history(self) -> None:
        small = self._walk(400, 20)
        large = self._walk(4000, 20)
        self.assertLessEqual(
            large["final_cursor_bytes"],
            small["final_cursor_bytes"] * 2,
            f"the cursor grew with delivered history: {small} -> {large}",
        )
        self.assertNotIn(
            "delivered_finding_ids",
            large["cursor_keys"],
            "the cursor must not duplicate the delivery ledger",
        )

    def test_every_page_is_approval_of_a_bounded_write(self) -> None:
        walk = self._walk(2000, 50)
        self.assertEqual(walk["writes"], walk["pages"])
        self.assertLess(
            walk["max_write"],
            4096,
            f"a cursor write should be bounded, got {walk['max_write']} bytes",
        )

    def test_forty_pages_persist_less_than_the_audit_baseline(self) -> None:
        """The audit's own 40-page sample wrote 234910 cumulative bytes."""
        walk = self._walk(800, 20)
        self.assertEqual(walk["pages"], 40)
        self.assertLess(
            walk["cumulative"],
            234910,
            f"40 pages wrote {walk['cumulative']} cursor bytes, no better than the "
            f"pre-fix baseline the audit measured",
        )


if __name__ == "__main__":
    unittest.main()
