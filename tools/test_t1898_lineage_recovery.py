"""T-1898: a frozen lineage head never recovers by itself.

Measured on this repository 2026-10-24: the v2 conformance lineage head sat at
`receipt_count 3669` while the receipt namespace held **3936** files, with a
`receipt_dir_mtime_ns` eight days older than the directory. Every bounded
lookup discarded itself and `conformance.latest_receipt` fell back to
`_receipt_content_inventory`, which re-hashed every receipt in the namespace.
Measured cost of that fallback on the live tree (3937 files, 8.6 MB):
**1.49 s per run**, against 1.8 ms for the bounded lookup, and it was
invisible: nothing reported the bounded path as broken.

The refusal in `advance_append` is correct and stays: a receipt the lineage was
not told about must never be adopted by a bounded guess (an out-of-band sibling
is exactly the case the existing lineage tests pin). The defect was that the
refusal had NO RECOVERY -- `rebuild_lineage` can restore the head, but nothing
called it for an already-stale head, and no CLI route exposed it. So one
out-of-band receipt, or one crash between the receipt write and the head
publish, froze the fast path for the remaining lifetime of the project.

Four properties must hold together, and these tests pin all four:

1. a stale head is DETECTED and the degraded answer stays TRUE;
2. the READ path stays read-only -- `saipen status` may not republish
   projection state (COMMANDS_REFERENCE.md documents `status` as read-only);
3. the WRITER path, which is already publishing projection documents, runs
   the canonical deep rebuild so the next reader gets the bounded path back;
4. a corrupt sibling refuses the repair instead of being laundered into a
   fresh-looking head, and a head that is already current costs one stat.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import conformance, conformance_lineage as CL

RECEIPTS = ".saipen/recovery/conformance"


def _write_receipt(root: Path, rid: str, gate: str, ts: str) -> Path:
    # The timestamp's colons are not legal in a Windows filename; the receipt
    # BODY keeps the exact canonical stamp, which is what the index reads.
    safe_ts = ts.replace(":", "")
    path = root / RECEIPTS / f"{safe_ts}_{rid}_{gate}_FAIL.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "kind": "conformance_receipt",
                "receipt_id": rid,
                "gate": gate,
                "timestamp_utc": ts,
                "verdict": "FAIL",
            }
        ),
        encoding="utf-8",
    )
    return path


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class FrozenHeadRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="t1898_"))
        self.addCleanup(shutil.rmtree, self.root, True)

    def _frozen(self) -> None:
        """A lineage head that no longer describes the receipt namespace."""
        for index in range(3):
            _write_receipt(self.root, f"r{index}", "core", f"2026-01-01T00:00:0{index}Z")
        first = CL.rebuild_lineage(self.root)
        self.assertTrue(first.get("ok"), first)
        # A receipt the lineage was never told about -- the out-of-band case.
        _write_receipt(self.root, "out-of-band", "core", "2026-01-01T00:00:59Z")
        self.assertTrue(self._stale(), "the fixture must actually freeze the head")

    def _stale(self) -> bool:
        head = CL._read_head(self.root)
        self.assertIsNotNone(head)
        return head[0].get("receipt_dir_mtime_ns") != CL._receipt_dir_mtime_ns(self.root)

    def _append_canonically(self, rid: str, ts: str) -> Path:
        """Mirror the canonical append: the pre-append directory token is
        captured BEFORE the receipt file exists."""
        prior = (self.root / RECEIPTS).stat().st_mtime_ns
        path = _write_receipt(self.root, rid, "core", ts)
        conformance._update_receipt_index(
            self.root,
            "core",
            rid,
            ts,
            receipt_path=path.relative_to(self.root).as_posix(),
            prior_receipt_dir_mtime_ns=prior,
        )
        return path

    def test_an_out_of_band_receipt_makes_the_head_stale(self) -> None:
        """Detection: the stale head is recognised, and the answer is TRUE.

        Detection alone was all that happened before T-1898 -- the lookup gave
        up and every later run re-scanned the whole namespace. The assertion
        that matters is the second one: whatever the degraded path answers must
        be what the namespace actually holds, never what the frozen head says.
        """
        self._frozen()
        handled, record = CL.latest_receipt_bounded(self.root, "core")
        self.assertTrue(handled, "a live v2 head must handle the lookup")
        self.assertIsNone(record, "a stale head must not authenticate an answer")
        self.assertEqual(conformance.latest_receipt(self.root, "core")["receipt_id"], "out-of-band")

    def test_the_read_path_stays_read_only(self) -> None:
        """`saipen status` is documented read-only, so the read path may NOT
        repair the head. It reports the truth and leaves every byte alone."""
        self._frozen()
        before = _snapshot(self.root)
        latest = conformance.latest_receipt(self.root, "core")
        self.assertEqual(latest["receipt_id"], "out-of-band")
        self.assertEqual(_snapshot(self.root), before, "the read path mutated the project")
        self.assertTrue(self._stale(), "the read path republished projection state")

    def test_the_writer_path_repairs_the_head_and_restores_the_bounded_path(self) -> None:
        """The whole point: one canonical append restores the fast path.

        Without the repair the head stays stale forever, so every later read
        pays the full-namespace scan. Here the bounded lookup must come back,
        and it must answer the TRUE latest -- the out-of-band receipt -- not
        the frozen head's `r2`.
        """
        self._frozen()
        self._append_canonically("r3", "2026-01-01T00:00:04Z")
        self.assertFalse(self._stale(), "the writer path must republish a head for the namespace")
        handled, record = CL.latest_receipt_bounded(self.root, "core")
        self.assertTrue(handled)
        self.assertIsNotNone(record)
        self.assertEqual(record["receipt_id"], "out-of-band")
        valid, errors = CL.validate_lineage_deep(self.root)
        self.assertTrue(valid, errors)

    def test_a_corrupt_sibling_refuses_the_repair_and_keeps_the_frozen_head(self) -> None:
        """Repair must never launder corrupt evidence into authority."""
        self._frozen()
        (self.root / RECEIPTS / "corrupt.json").write_text("{not json", encoding="utf-8")
        head_before = CL._read_head(self.root)
        locator_before = CL._read_locator(self.root, "core")
        self._append_canonically("r3", "2026-01-01T00:00:04Z")
        self.assertEqual(CL._read_head(self.root), head_before, "a corrupt sibling was blessed")
        self.assertEqual(CL._read_locator(self.root, "core"), locator_before)
        # Still fails closed for readers.
        with self.assertRaises(conformance.ReceiptDiscoveryError):
            conformance.latest_receipt(self.root, "core")

    def test_a_current_head_costs_one_stat_not_a_rebuild(self) -> None:
        """The repair hook must not make every canonical append pay a deep
        scan: when the head already describes the namespace, nothing rebuilds."""
        for index in range(3):
            _write_receipt(self.root, f"r{index}", "core", f"2026-01-01T00:00:0{index}Z")
        self.assertTrue(CL.rebuild_lineage(self.root).get("ok"))
        with mock.patch.object(
            CL, "rebuild_lineage", wraps=CL.rebuild_lineage
        ) as rebuild:
            self.assertTrue(CL.repair_stale_head(self.root))
        self.assertEqual(rebuild.call_count, 0, "a current head must not trigger a rebuild")


if __name__ == "__main__":
    unittest.main()
