"""T-1283 -- the bounded conformance lineage must ingest a MIXED-SCHEMA receipt
population, because the engine's own receipt grammar admits one.

`_RECEIPT_REQUIRED_FIELDS_V1` deliberately omits `receipt_id`, and
`_iter_receipts` accepts a v1 receipt, so a real project can hold receipts that
carry no id of their own. `_scan_receipt_members` read `record["receipt_id"]`
unconditionally, which made the lineage STRICTLY less permissive than the
canonical scan it exists to accelerate: the first append into such a population
raised KeyError out of `generate_conformance_receipt` AFTER the receipt bytes
were already durable, so no index was ever updated and every later lookup
full-scanned the whole population forever.

Each test here is written so it goes RED against the pre-fix code. They run on
small synthetic roots; the scaling claims are proved by counting, never by
timing, because AC-02/AC-03/AC-04 say so explicitly.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from saipen_engine import conformance as C
from saipen_engine import conformance_lineage as CL


LEGACY_TS = "2026-08-20T06:35:38Z"


def _v1_receipt(gate: str, ts: str) -> dict:
    """A schema_version 1 receipt: legitimate under _RECEIPT_REQUIRED_FIELDS_V1,
    and carrying no receipt_id of its own."""
    return {
        "kind": "conformance_receipt",
        "schema_version": 1,
        "gate": gate,
        "timestamp_utc": ts,
        "verdict": "FAIL",
        "exit_code": 1,
        "validator_protocol_version": "1",
        "content_hash": "0" * 16,
    }


def _v2_receipt(gate: str, ts: str, rid: str) -> dict:
    doc = _v1_receipt(gate, ts)
    doc["schema_version"] = 2
    doc["receipt_id"] = rid
    return doc


class LegacyIngestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="t1283-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.rdir = self.root / C.RECEIPT_DIRNAME
        self.rdir.mkdir(parents=True)

    def _write(self, doc: dict, name: str) -> None:
        (self.rdir / name).write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")

    def _write_legacy(self) -> None:
        self._write(_v1_receipt("core", LEGACY_TS), "2026-08-20T063538Z_core_FAIL.json")

    def _count_receipt_reads(self, fn):
        """Count how many receipt evidence files fn opens. AC-04 asks this by
        count, not by clock."""
        reads: list[str] = []

        def classify(path: Path):
            s = str(path).replace("\\", "/")
            if f"/{C.RECEIPT_DIRNAME}/" not in s:
                return None
            tail = s.split(f"/{C.RECEIPT_DIRNAME}/", 1)[1]
            if tail.startswith("index/"):
                return None
            return tail

        real_bytes = Path.read_bytes

        def counting_bytes(self):
            key = classify(self)
            if key is not None:
                reads.append(key)
            return real_bytes(self)

        Path.read_bytes = counting_bytes
        try:
            fn()
        finally:
            Path.read_bytes = real_bytes
        return reads


class TestLegacyIngest(LegacyIngestBase):
    def test_v1_receipt_is_accepted_by_the_canonical_scan(self) -> None:
        """The premise. If this fails the engine no longer admits v1 receipts and
        the whole ticket is moot."""
        self._write(_v1_receipt("core", LEGACY_TS), "2026-08-20T063538Z_core_FAIL.json")
        recs = C._iter_receipts(self.root)
        self.assertEqual(len(recs), 1)
        self.assertNotIn("receipt_id", recs[0])

    def test_deep_rebuild_ingests_a_v1_receipt(self) -> None:
        """RED against pre-fix code: raised KeyError: 'receipt_id'."""
        self._write(_v1_receipt("core", LEGACY_TS), "2026-08-20T063538Z_core_FAIL.json")
        self._write(_v2_receipt("core", "2026-08-20T07:00:00Z", "receipt-aaa"), "b.json")
        result = CL.rebuild_lineage(self.root)
        self.assertTrue(result["ok"], result)

    def test_deep_audit_ingests_a_v1_receipt(self) -> None:
        """RED against pre-fix code: validate_lineage_deep raised KeyError too."""
        self._write(_v1_receipt("core", LEGACY_TS), "2026-08-20T063538Z_core_FAIL.json")
        self._write(_v2_receipt("core", "2026-08-20T07:00:00Z", "receipt-aaa"), "b.json")
        CL.rebuild_lineage(self.root)
        ok, errors = CL.validate_lineage_deep(self.root)
        self.assertTrue(ok, errors)

    def test_legacy_identity_is_content_addressed_and_stable(self) -> None:
        """The derived id must be deterministic, and must not collide with an
        issued W2-005 id."""
        self._write(_v1_receipt("core", LEGACY_TS), "2026-08-20T063538Z_core_FAIL.json")
        raw = (self.rdir / "2026-08-20T063538Z_core_FAIL.json").read_bytes()
        import hashlib

        digest = hashlib.sha256(raw).hexdigest()
        first = CL._member_receipt_id(_v1_receipt("core", "2026-08-20T06:35:38Z"), digest)
        second = CL._member_receipt_id(_v1_receipt("core", "2026-08-20T06:35:38Z"), digest)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("legacy-"))
        self.assertIn(digest[:32], first)
        # different bytes -> different id
        self.assertNotEqual(first, CL._member_receipt_id({}, "f" * 64))
        # a real id is never rewritten
        self.assertEqual(
            CL._member_receipt_id({"receipt_id": "receipt-zzz"}, digest), "receipt-zzz"
        )

    def test_append_over_a_v1_population_does_not_raise(self) -> None:
        """RED against pre-fix code: the KeyError escaped generate_conformance_receipt
        after the receipt bytes were already written."""
        self._write(_v1_receipt("core", LEGACY_TS), "2026-08-20T063538Z_core_FAIL.json")
        rec = C.generate_conformance_receipt(project_root=self.root, gate="core", exit_code=1)
        self.assertTrue(rec.get("receipt_id"))
        self.assertIsNotNone(CL._read_head(self.root), "append must establish the v2 lineage")


class TestBoundedLookup(LegacyIngestBase):
    def _seed(self, n: int = 12) -> str:
        for i in range(n):
            self._write(
                _v2_receipt("core", f"2026-08-2{i % 9}T00:00:{i:02d}.000000Z", f"receipt-{i:03d}"),
                f"r{i:03d}.json",
            )
        self._write(_v1_receipt("core", "2026-08-01T00:00:00Z"), "legacy.json")
        CL.rebuild_lineage(self.root)
        return "core"

    def test_bounded_lookup_equals_the_strict_scan(self) -> None:
        gate = self._seed()
        bounded = C.latest_receipt(self.root, gate)
        strict = [
            r
            for r in C._iter_receipts(self.root)
            if r.get("gate") == gate
        ]
        from saipen_engine.board import iso_utc_sort_key

        earliest = iso_utc_sort_key("0000-01-01T00:00:00Z")

        def order(r):
            key = iso_utc_sort_key(r.get("timestamp_utc", "")) or earliest
            return (key, r.get("receipt_id") or "")

        expected = max(strict, key=order)
        self.assertEqual(bounded.get("receipt_id"), expected.get("receipt_id"))

    def test_bounded_lookup_does_not_scale_with_the_population(self) -> None:
        """AC-03 by COUNT, never by timing: growing the population must not grow
        the number of receipts a single latest lookup opens."""
        gate = self._seed(n=8)
        small = self._count_receipt_reads(lambda: C.latest_receipt(self.root, gate))
        for i in range(8, 120):
            ts = f"2026-09-01T00:{i % 60:02d}:{i % 60:02d}.{i:06d}Z"
            self._write(_v2_receipt("core", ts, f"receipt-b{i:03d}"), f"b{i:03d}.json")
        CL.rebuild_lineage(self.root)
        large = self._count_receipt_reads(lambda: C.latest_receipt(self.root, gate))
        self.assertLessEqual(len(large), len(small) + 1, (len(small), len(large)))

    def test_append_does_not_reread_sealed_generations(self) -> None:
        """AC-04: a fold inside the active segment reads the active tail only."""
        gate = self._seed(n=CL.GEN_BOUND * 2 + 3)
        reads = self._count_receipt_reads(
            lambda: C.generate_conformance_receipt(project_root=self.root, gate=gate, exit_code=1)
        )
        population = len(list(self.rdir.glob("*.json")))
        self.assertLess(len(reads), population / 2, (len(reads), population))
        self.assertLessEqual(len(reads), CL.GEN_BOUND + 1)

    def test_exact_bytes_stay_authoritative(self) -> None:
        """AC-05: a receipt whose BYTES no longer match its member digest is
        caught. Rewritten as valid JSON so the parse gate still passes and only
        the digest authority is under test."""
        self._seed()
        victim = self.rdir / "r003.json"
        doc = json.loads(victim.read_text(encoding="utf-8"))
        doc["verdict"] = "PASS"
        victim.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
        ok, errors = CL.validate_lineage_deep(self.root)
        self.assertFalse(ok)
        self.assertTrue(errors)

    def test_out_of_band_sibling_is_degraded_never_laundered(self) -> None:
        """AC-06 red control: an out-of-band file moves the directory mtime, so
        the bounded path must REFUSE and the caller must fall back to the strict
        scan -- it must never serve a record the head does not authenticate."""
        gate = self._seed()
        handled, record = CL.latest_receipt_bounded(self.root, gate)
        self.assertTrue(handled)
        self.assertIsNotNone(record, "a clean tree must be served by the bounded path")
        (self.rdir / "zz_oob.json").write_text(
            json.dumps(
                {
                    "kind": "conformance_receipt",
                    "schema_version": 2,
                    "receipt_id": "oob",
                    "gate": gate,
                    "timestamp_utc": "2099-01-01T00:00:00.000000Z",
                    "verdict": "PASS",
                    "exit_code": 0,
                    "validator_protocol_version": "1",
                }
            ),
            encoding="utf-8",
        )
        handled2, record2 = CL.latest_receipt_bounded(self.root, gate)
        self.assertTrue(handled2, "a live head must still be honoured as authority")
        self.assertIsNone(record2, "an unlocatable namespace must degrade, never launder")

    def test_tampered_referenced_generation_degrades(self) -> None:
        """AC-06 red control: the generation the locator actually references is
        part of the authentication chain; corrupting it must degrade."""
        gate = self._seed()
        locator = CL._read_locator(self.root, gate)
        self.assertIsNotNone(locator)
        path = CL._index_path(self.root, f"{CL.INDEX_DIR_REL}/{locator['generation_id']}.json")
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["members"] = list(reversed(doc.get("members") or []))
        path.write_text(json.dumps(doc), encoding="utf-8")
        _handled, record = CL.latest_receipt_bounded(self.root, gate)
        self.assertIsNone(record, "a tampered generation must never yield a record")

    def test_foreign_object_is_refused_fail_closed(self) -> None:
        """AC-06 red control: the lineage must not seed from a population it
        cannot vouch for. The refusal is the point -- a foreign object raises
        rather than being silently skipped into a partial membership."""
        self._seed()
        (self.rdir / "zz_foreign.json").write_text(
            json.dumps({"not": "a receipt"}), encoding="utf-8"
        )
        with self.assertRaises(C.ReceiptDiscoveryError):
            CL.rebuild_lineage(self.root)
        # the pre-existing authority is left untouched, so reads still work
        handled, _record = CL.latest_receipt_bounded(self.root, "core")
        self.assertTrue(handled)


if __name__ == "__main__":
    unittest.main(verbosity=2)
