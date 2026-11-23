"""R010 structural tests: bounded settled-journal projection (SRC-025:R010).

The counters are structural (decodes, receipt opens, sealed-segment reads),
never wall-clock: hot operation lookup must cost the locator + relevant
segment(s) + active tail, not the lifetime settled population.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import journal  # noqa: E402
from saipen_engine import settled_projection as SP  # noqa: E402
from saipen_engine.journal import OPS_DIR, SETTLED_DIR  # noqa: E402
from saipen_engine.paths import runtime_lock_identity  # noqa: E402

_TARGET = {
    "path": ".saipen/kitchen/_perf_test.json",
    "role": "generic",
    "before_hash": "",
    "after_hash": "x",
    "applied": True,
    "action": "write",
    "content": "{}",
}


def _write_receipt(root: Path, op_id: str, operation: str, ns: str = "settled") -> dict:
    base = root / (OPS_DIR if ns == "ops" else SETTLED_DIR) / op_id
    base.mkdir(parents=True, exist_ok=True)
    record = {
        "op_id": op_id,
        "status": "COMMITTED",
        "operation": operation,
        "semantic_payload_hash": "x",
        "created_at": "2026-09-07T00:00:00Z",
        "agent": "perf-wave",
        "project_identity": runtime_lock_identity(root),
        "verification_policy": "none",
        "preconditions": {},
        "progress_index": 0,
        "targets": [dict(_TARGET)],
    }
    (base / "operation.json").write_text(json.dumps(record))
    return record


def _canonical_settle(root: Path, op_id: str, operation: str, *, prior_token: int | None = None):
    """Mirror the settlement contract: pre-move token + moved identity."""
    if prior_token is None:
        prior_token = SP._settled_dir_token(root)
    _write_receipt(root, op_id, operation)
    return SP.advance_after_settlement(
        root, moved_names=[op_id], prior_settled_dir_mtime_ns=prior_token
    )


class SettledProjectionTests(unittest.TestCase):
    def test_zero_match_never_enumerates_settled_namespace(self) -> None:
        """R010-A red control: a hot zero-match lookup must not enumerate
        the lifetime settled namespace, whatever the population."""
        for population in (100, 1000, 10000):
            with self.subTest(population=population):
                root = Path(tempfile.mkdtemp(prefix=f"r010a_{population}_"))
                try:
                    for index in range(population):
                        _write_receipt(root, f"op-{index:06d}", "alpha")
                    SP.rebuild_projection(root)
                    enumerated = {"n": 0}
                    original_iterdir = Path.iterdir

                    def counting_iterdir(path_self, *args, **kwargs):
                        text = str(path_self)
                        if "\\settled" in text or "/settled" in text:
                            enumerated["n"] += 1
                        return original_iterdir(path_self, *args, **kwargs)

                    with mock.patch.object(Path, "iterdir", counting_iterdir):
                        records, errors = journal.semantic_receipts_for_operation_safe(
                            root, "no-such-operation"
                        )
                    self.assertEqual(records, [])
                    self.assertEqual(errors, ())
                    # Independent of population: zero lifetime namespace
                    # enumerations on the hot read (staleness is one stat).
                    self.assertEqual(
                        enumerated["n"],
                        0,
                        f"population {population}: hot lookup enumerated "
                        f"the settled namespace",
                    )
                finally:
                    shutil.rmtree(root, ignore_errors=True)

    def test_normal_append_does_not_scale_with_sealed_segment_count(self) -> None:
        """R010-B red control: one normal append across growing sealed
        histories reads only the active tail, the moved receipt and its
        locators -- never a sealed segment."""
        for sealed_segments in (1, 4, 8, 32):
            with self.subTest(sealed_segments=sealed_segments):
                root = Path(tempfile.mkdtemp(prefix=f"r010b_{sealed_segments}_"))
                try:
                    for index in range(sealed_segments * SP.SEG_BOUND):
                        _write_receipt(root, f"op-{index:06d}", "alpha")
                    SP.rebuild_projection(root)
                    segment_reads = {"n": 0}
                    enumerated = {"n": 0}
                    receipt_opens = {"n": 0}
                    original_iterdir = Path.iterdir
                    original_read = Path.read_bytes

                    def counting_iterdir(path_self, *args, **kwargs):
                        text = str(path_self)
                        if "\\settled" in text or "/settled" in text:
                            enumerated["n"] += 1
                        return original_iterdir(path_self, *args, **kwargs)

                    def counting_read(path_self, *args, **kwargs):
                        text = str(path_self)
                        if (
                            text.endswith(".json")
                            and ("\\settled-index\\seg-" in text or "/settled-index/seg-" in text)
                            and "\\loc\\" not in text
                            and "/loc/" not in text
                        ):
                            segment_reads["n"] += 1
                        if text.endswith("operation.json") and (
                            "\\settled\\" in text or "/settled/" in text
                        ):
                            receipt_opens["n"] += 1
                        return original_read(path_self, *args, **kwargs)

                    with mock.patch.object(
                        Path, "iterdir", counting_iterdir
                    ), mock.patch.object(Path, "read_bytes", counting_read):
                        result = _canonical_settle(
                            root, "beta-0001", "beta"
                        )
                    self.assertTrue(result["ok"], result)
                    self.assertEqual(result["code"], "SETTLED_PROJECTION_ADVANCED", result)
                    # A normal append is bounded by the active tail, the
                    # directly affected locator(s) and the moved receipt --
                    # sealed segment reads and namespace enumeration must NOT
                    # scale with the sealed history size.
                    self.assertEqual(segment_reads["n"], 0)
                    self.assertEqual(enumerated["n"], 0)
                    self.assertEqual(receipt_opens["n"], 1)
                finally:
                    shutil.rmtree(root, ignore_errors=True)

    def test_seal_relocates_only_bounded_affected_locators(self) -> None:
        """Sealing the full tail relocates exactly the operations present in
        that tail (bounded by SEG_BOUND) and preserves earlier sealed
        references."""
        root = Path(tempfile.mkdtemp(prefix="r010_seal_loc_"))
        try:
            for index in range(SP.SEG_BOUND):
                _write_receipt(root, f"op-{index:04d}", "alpha" if index < 64 else "zeta")
            SP.rebuild_projection(root)
            _canonical_settle(root, "op-0128", "alpha")
            head = SP._read_head(root)
            self.assertEqual(head[0]["sealed_count"], 1)
            # Alpha: sealed references preserved, ACTIVE reference relocated
            # to seg-0000, and the newly settled receipt folded into a fresh
            # ACTIVE tail entry.
            entries = SP._read_locator(root, "alpha")
            self.assertEqual(
                entries, [{"loc": "seg-0000", "names": [f"op-{index:04d}" for index in range(64)]},
                          {"loc": "active", "names": ["op-0128"]}]
            )
            entries = SP._read_locator(root, "zeta")
            self.assertEqual(
                entries,
                [{"loc": "seg-0000", "names": [f"op-{index:04d}" for index in range(64, 128)]}],
            )
            # Bounded lookup still returns everything for alpha.
            records, errors = journal.semantic_receipts_for_operation_safe(root, "alpha")
            self.assertEqual(errors, ())
            self.assertEqual(len(records), 65)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_crash_shaped_token_mismatch_fails_closed(self) -> None:
        """A receipt moved after the head's token (crash between move and
        advance) refuses bounded trust on the next hot read."""
        root = Path(tempfile.mkdtemp(prefix="r010_crash_"))
        try:
            _write_receipt(root, "op-0000", "alpha")
            SP.rebuild_projection(root)
            _write_receipt(root, "op-0001", "alpha")  # crash-shaped: no advance
            records, errors = journal.semantic_receipts_for_operation_safe(root, "alpha")
            self.assertEqual(records, [])
            self.assertTrue(any("stale" in message for message in errors))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_direct_caller_without_token_rebuilds_canonically(self) -> None:
        """A direct caller with no pre-move token never gets the bounded fold
        guess; the canonical rebuild covers the moved receipt."""
        root = Path(tempfile.mkdtemp(prefix="r010_direct_"))
        try:
            _write_receipt(root, "op-0000", "alpha")
            SP.rebuild_projection(root)
            _write_receipt(root, "op-0001", "alpha")
            result = SP.advance_after_settlement(root)  # no token, no moved id
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["code"], "SETTLED_PROJECTION_REBUILT", result)
            records, errors = journal.semantic_receipts_for_operation_safe(root, "alpha")
            self.assertEqual(errors, ())
            self.assertEqual(len(records), 2)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_rebuild_and_advance_publish_bounded_projection(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_rebuild_"))
        try:
            _write_receipt(root, "op-0000", "alpha")
            result = SP.rebuild_projection(root)
            self.assertTrue(result["ok"], result)
            self.assertTrue((root / SP.INDEX_DIR_REL / "head.json").is_file())
            result = _canonical_settle(root, "op-0001", "alpha")
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["settled_count"], 2)
            records, errors = journal.semantic_receipts_for_operation_safe(root, "alpha")
            self.assertEqual(errors, ())
            self.assertEqual(len(records), 2)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_zero_match_query_never_decodes_or_opens_lifetime_receipts(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_zero_"))
        try:
            for index in range(SP.SEG_BOUND + 1):
                _write_receipt(root, f"op-{index:04d}", "beta" if index % 3 == 0 else "alpha")
            SP.rebuild_projection(root)
            decodes = 0
            settled_opens = 0
            original_decode = journal.decode_operation_record
            original_read = Path.read_bytes

            def counting_decode(*args, **kwargs):
                nonlocal decodes
                decodes += 1
                return original_decode(*args, **kwargs)

            def counting_read(path_self, *args, **kwargs):
                nonlocal settled_opens
                text = str(path_self)
                if "\\settled\\" in text or "/settled/" in text:
                    settled_opens += 1
                return original_read(path_self, *args, **kwargs)

            with mock.patch.object(
                journal, "decode_operation_record", side_effect=counting_decode
            ), mock.patch.object(Path, "read_bytes", counting_read):
                records, errors = journal.semantic_receipts_for_operation_safe(root, "gamma")
            self.assertEqual(records, [])
            self.assertEqual(errors, ())
            self.assertEqual(decodes, 0, "zero-match query decoded a receipt")
            self.assertEqual(settled_opens, 0, "zero-match query opened a settled receipt")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_match_query_cost_bounded_by_relevant_segments(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_match_"))
        try:
            for index in range(SP.SEG_BOUND + 1):
                _write_receipt(root, f"op-{index:04d}", "beta" if index % 3 == 0 else "alpha")
            SP.rebuild_projection(root)
            decodes = 0
            original_decode = journal.decode_operation_record

            def counting_decode(*args, **kwargs):
                nonlocal decodes
                decodes += 1
                return original_decode(*args, **kwargs)

            with mock.patch.object(journal, "decode_operation_record", side_effect=counting_decode):
                records, errors = journal.semantic_receipts_for_operation_safe(root, "beta")
            self.assertEqual(errors, ())
            expected = sum(1 for index in range(SP.SEG_BOUND + 1) if index % 3 == 0)
            self.assertEqual(len(records), expected)
            self.assertLessEqual(decodes, SP.SEG_BOUND)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_append_below_bound_never_reads_sealed_bodies(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_append_"))
        try:
            for index in range(SP.SEG_BOUND):
                _write_receipt(root, f"op-{index:04d}", "alpha")
            SP.rebuild_projection(root)
            original_read_bytes = Path.read_bytes

            counter = {"n": 0}

            def counting_read(self, *args, **kwargs):
                text = str(self)
                if "\\settled\\op-0" in text and text.endswith("operation.json"):
                    counter["n"] += 1
                return original_read_bytes(self, *args, **kwargs)

            with mock.patch.object(Path, "read_bytes", counting_read):
                result = _canonical_settle(root, "beta-0001", "beta")
            self.assertTrue(result["ok"], result)
            # The newly moved receipt (beta) was opened; the 128 sealed alpha
            # bodies (op-0xxx) were never re-read or re-hashed.
            self.assertEqual(counter["n"], 0)
            head = SP._read_head(root)
            self.assertIsNotNone(head)
            self.assertEqual(head[0]["sealed_count"], 1)
            self.assertEqual(head[0]["settled_count"], SP.SEG_BOUND + 1)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_population_scaling_counters(self) -> None:
        """100 / 1,000 / 10,000 receipts: hot cost stays bounded, not lifetime."""
        for population in (100, 1000, 10000):
            with self.subTest(population=population):
                root = Path(tempfile.mkdtemp(prefix=f"r010_scale{population}_"))
                try:
                    for index in range(population):
                        _write_receipt(
                            root,
                            f"op-{index:06d}",
                            "beta" if index % 97 == 0 else "alpha",
                        )
                    SP.rebuild_projection(root)
                    original_decode = journal.decode_operation_record
                    counter = {"decodes": 0, "opens": 0}
                    original_read = Path.read_bytes

                    def counting_decode(*args, **kwargs):
                        counter["decodes"] += 1
                        return original_decode(*args, **kwargs)

                    def counting_read(path_self, *args, **kwargs):
                        text = str(path_self)
                        if text.endswith("operation.json") and (
                            "\\settled\\" in text or "/settled/" in text
                        ):
                            counter["opens"] += 1
                        return original_read(path_self, *args, **kwargs)

                    # Zero matches: nothing is opened or decoded.
                    counter["decodes"] = 0
                    counter["opens"] = 0
                    with mock.patch.object(
                        journal, "decode_operation_record", side_effect=counting_decode
                    ), mock.patch.object(Path, "read_bytes", counting_read):
                        records, errors = journal.semantic_receipts_for_operation_safe(
                            root, "no-such-operation"
                        )
                    self.assertEqual(errors, ())
                    self.assertEqual(records, [])
                    self.assertEqual(counter["decodes"], 0)
                    self.assertEqual(counter["opens"], 0)

                    # One gate of matches: cost bounded by the relevant
                    # segment(s), never by the population.
                    counter["decodes"] = 0
                    counter["opens"] = 0
                    expected = (population + 96) // 97
                    with mock.patch.object(
                        journal, "decode_operation_record", side_effect=counting_decode
                    ), mock.patch.object(Path, "read_bytes", counting_read):
                        records, errors = journal.semantic_receipts_for_operation_safe(
                            root, "beta"
                        )
                    self.assertEqual(errors, ())
                    self.assertEqual(len(records), expected)
                    self.assertLessEqual(counter["decodes"], SP.SEG_BOUND + expected)
                    self.assertLessEqual(counter["opens"], SP.SEG_BOUND + expected)
                finally:
                    shutil.rmtree(root, ignore_errors=True)

    def test_seal_happens_exactly_once_at_the_bound(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_seal_"))
        try:
            for index in range(SP.SEG_BOUND):
                _write_receipt(root, f"op-{index:04d}", "alpha")
            SP.rebuild_projection(root)
            head = SP._read_head(root)
            self.assertIsNotNone(head)
            self.assertEqual(head[0]["sealed_count"], 0)
            _write_receipt(root, "op-0128", "alpha")
            _canonical_settle(root, "op-0128", "alpha")
            head = SP._read_head(root)
            self.assertIsNotNone(head)
            self.assertEqual(head[0]["sealed_count"], 1)
            self.assertEqual(head[0]["latest_sealed_id"], "seg-0000")
            # The next advance (nothing new) is idempotent and does not re-seal.
            result = SP.advance_after_settlement(
                root,
                moved_names=[],
                prior_settled_dir_mtime_ns=SP._settled_dir_token(root),
            )
            self.assertEqual(result["code"], "SETTLED_PROJECTION_CURRENT")
            head = SP._read_head(root)
            self.assertEqual(head[0]["sealed_count"], 1)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_tampered_relevant_receipt_fails_closed(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_tamper_"))
        try:
            _write_receipt(root, "op-0000", "alpha")
            SP.rebuild_projection(root)
            manifest = root / SETTLED_DIR / "op-0000" / "operation.json"
            manifest.write_text(manifest.read_text().replace('"alpha"', '"beta"'))
            records, errors = journal.semantic_receipts_for_operation_safe(root, "alpha")
            self.assertEqual(records, [])
            self.assertTrue(any("op-0000" in message for message in errors))
            self.assertTrue(any("digest mismatch" in message for message in errors))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_tampered_unrelated_sealed_receipt_leaves_hot_lookup_clean_and_deep_red(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_unrelated_"))
        try:
            for index in range(SP.SEG_BOUND):
                _write_receipt(root, f"op-{index:04d}", "alpha")
            _write_receipt(root, "beta-0001", "beta")
            SP.rebuild_projection(root)
            manifest = root / SETTLED_DIR / "op-0000" / "operation.json"
            manifest.write_text(manifest.read_text().replace('"alpha"', '"tampered"'))
            records, errors = journal.semantic_receipts_for_operation_safe(root, "beta")
            self.assertEqual(errors, ())
            self.assertEqual([r["op_id"] for r in records], ["beta-0001"])
            deep_ok, deep_errors = SP.validate_projection_deep(root)
            self.assertFalse(deep_ok)
            self.assertTrue(any("op-0000" in message for message in deep_errors))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_corrupt_projection_head_fails_closed_instead_of_legacy_scan(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_head_"))
        try:
            _write_receipt(root, "op-0000", "alpha")
            SP.rebuild_projection(root)
            head_path = root / SP.INDEX_DIR_REL / "head.json"
            head_path.write_text("{broken")
            records, errors = journal.semantic_receipts_for_operation_safe(root, "alpha")
            self.assertEqual(records, [])
            self.assertTrue(errors, "corrupt projection authority must fail closed")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_stale_projection_detected_without_opening_receipts(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_stale_"))
        try:
            _write_receipt(root, "op-0000", "alpha")
            SP.rebuild_projection(root)
            # A crash between the move and the advance: receipt on disk the
            # projection never saw.
            _write_receipt(root, "op-0001", "alpha")
            records, errors = journal.semantic_receipts_for_operation_safe(root, "alpha")
            self.assertEqual(records, [])
            self.assertTrue(any("stale" in message for message in errors))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_absent_projection_falls_back_to_canonical_scan_readonly(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_absent_"))
        try:
            _write_receipt(root, "op-0000", "alpha")
            records, errors = journal.semantic_receipts_for_operation_safe(root, "alpha")
            self.assertEqual(errors, ())
            self.assertEqual(len(records), 1)
            self.assertFalse((root / SP.INDEX_DIR_REL).exists(), "read-only lookup must not mutate")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_settlement_advances_after_stale_projection(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_advance_"))
        try:
            _write_receipt(root, "op-0000", "alpha")
            SP.rebuild_projection(root)
            _write_receipt(root, "op-0001", "alpha")  # crash-shaped stale state
            result = SP.advance_after_settlement(root)
            self.assertTrue(result["ok"], result)
            head = SP._read_head(root)
            self.assertEqual(head[0]["settled_count"], 2)
            records, errors = journal.semantic_receipts_for_operation_safe(root, "alpha")
            self.assertEqual(errors, ())
            self.assertEqual(len(records), 2)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_ops_namespace_matches_stay_visible_on_bounded_path(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_ops_"))
        try:
            _write_receipt(root, "op-0000", "alpha")
            SP.rebuild_projection(root)
            _write_receipt(root, "live-0001", "alpha", ns="ops")
            records, errors = journal.semantic_receipts_for_operation_safe(root, "alpha")
            self.assertEqual(errors, ())
            self.assertEqual(len(records), 2)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_bounded_records_equal_snapshot_records(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="r010_equiv_"))
        try:
            for index in range(10):
                _write_receipt(root, f"op-{index:04d}", "alpha" if index % 2 else "beta")
            _write_receipt(root, "live-0001", "alpha", ns="ops")
            SP.rebuild_projection(root)
            bounded, errors = journal.semantic_receipts_for_operation_safe(root, "alpha")
            self.assertEqual(errors, ())
            snapshot_records, snapshot_errors = journal.semantic_receipt_snapshot(root)
            self.assertFalse(snapshot_errors)
            snapshot_alpha = [r for r in snapshot_records if r.get("operation") == "alpha"]
            self.assertEqual(
                [r["op_id"] for r in bounded], [r["op_id"] for r in snapshot_alpha]
            )
        finally:
            shutil.rmtree(root, ignore_errors=True)


def _write_convergence_fixture(root: Path) -> object:
    from freshness import compute_source_identity

    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    app_bytes = b"print('ok')\n"
    (src / "app.py").write_bytes(app_bytes)
    (root / ".saipen").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "IDENTITY.md").write_text(
        "---\nproject_lineage: lineage-" + "1" * 32 + "\n---\n",
        encoding="utf-8",
    )
    source_id = compute_source_identity(root)
    for index in range(SP.SEG_BOUND + 5):
        _write_receipt(root, f"op-{index:04d}", "alpha")
    stages = [
        ("E", "PASS", "2026-09-07T00:00:01Z", "E-001"),
        ("F", "CLEAN", "2026-09-07T00:00:02Z", "E-002"),
        ("G", "COMPLETED", "2026-09-07T00:00:03Z", "E-003"),
        ("H", "PASS", "2026-09-07T00:00:04Z", "E-004"),
        ("I", "CLEAN", "2026-09-07T00:00:05Z", "E-005"),
    ]
    for stage, verdict, ts, eid in stages:
        meta = {
            "operation": "convergence_stage",
            "status": "COMMITTED",
            "stage": stage,
            "verdict": verdict,
            "event_id": eid,
            "source_head": source_id.source_head,
            "source_tree_fingerprint": source_id.source_tree_fingerprint,
        }
        if stage == "G":
            meta["input_source_head"] = source_id.source_head
            meta["input_source_tree_fingerprint"] = source_id.source_tree_fingerprint
            meta["resulting_source_head"] = source_id.source_head
            meta["resulting_source_tree_fingerprint"] = source_id.source_tree_fingerprint
        rec = _write_receipt(root, f"conv-{stage}", "convergence_stage")
        rec["created_at"] = ts
        rec["receipt_metadata"] = meta
        (root / SETTLED_DIR / f"conv-{stage}" / "operation.json").write_text(
            json.dumps(rec), encoding="utf-8"
        )
    defer_rec = _write_receipt(root, "defer-0001", "crew_defer")
    defer_rec["created_at"] = "2026-09-07T00:00:06Z"
    defer_rec["receipt_metadata"] = {
        "operation": "crew_defer",
        "status": "COMMITTED",
        "project_identity": runtime_lock_identity(root),
        "project_lineage": "lineage-" + "1" * 32,
        "ticket_id": "T-1",
        "paths": {"src/app.py": journal.hash_bytes(app_bytes)},
    }
    (root / SETTLED_DIR / "defer-0001" / "operation.json").write_text(
        json.dumps(defer_rec), encoding="utf-8"
    )
    SP.rebuild_projection(root)
    return source_id


class ConvergenceBoundedProjectionTests(unittest.TestCase):
    def test_convergence_verdict_uses_bounded_projection_without_snapshot_scan(self) -> None:
        from saipen_engine import convergence

        root = Path(tempfile.mkdtemp(prefix="r010_conv_"))
        try:
            for index in range(SP.SEG_BOUND + 5):
                _write_receipt(root, f"op-{index:04d}", "alpha")
            SP.rebuild_projection(root)
            calls = 0
            original_snapshot = journal.semantic_receipt_snapshot

            def counting_snapshot(*args, **kwargs):
                nonlocal calls
                calls += 1
                return original_snapshot(*args, **kwargs)

            with mock.patch.object(
                journal, "semantic_receipt_snapshot", side_effect=counting_snapshot
            ):
                bounded = convergence.convergence_verdict(root)
            self.assertEqual(
                calls,
                0,
                "convergence_verdict(receipt_snapshot=None) scanned lifetime receipts "
                "when projection was CURRENT",
            )
            full_snapshot = journal.semantic_receipt_snapshot(root)
            full = convergence.convergence_verdict(root, receipt_snapshot=full_snapshot)
            self.assertEqual(bounded.as_dict(), full.as_dict())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_convergence_verdict_full_chain_and_crew_defer_parity(self) -> None:
        from saipen_engine import convergence

        root = Path(tempfile.mkdtemp(prefix="r010_conv_full_"))
        try:
            source_id = _write_convergence_fixture(root)
            calls = 0
            original_snapshot = journal.semantic_receipt_snapshot

            def counting_snapshot(*args, **kwargs):
                nonlocal calls
                calls += 1
                return original_snapshot(*args, **kwargs)

            with mock.patch.object(
                journal, "semantic_receipt_snapshot", side_effect=counting_snapshot
            ):
                bounded = convergence.convergence_verdict(root, source_id=source_id)
            self.assertEqual(calls, 0)
            self.assertTrue(bounded.ok, bounded.reasons)
            self.assertEqual(len(bounded.stages), 5)
            self.assertEqual(bounded.attribution_problems, ())
            full_snapshot = journal.semantic_receipt_snapshot(root)
            full = convergence.convergence_verdict(
                root, source_id=source_id, receipt_snapshot=full_snapshot
            )
            self.assertEqual(bounded.as_dict(), full.as_dict())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_convergence_verdict_fails_closed_when_projection_corrupt(self) -> None:
        from saipen_engine import convergence

        root = Path(tempfile.mkdtemp(prefix="r010_conv_bad_"))
        try:
            _write_receipt(root, "op-0000", "alpha")
            SP.rebuild_projection(root)
            (root / SP.INDEX_DIR_REL / "head.json").write_text("{broken", encoding="utf-8")
            verdict = convergence.convergence_verdict(root)
            self.assertFalse(verdict.ok)
            self.assertTrue(any("corruption" in r for r in verdict.reasons), verdict.reasons)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_convergence_verdict_fails_closed_when_crew_defer_locator_corrupt(self) -> None:
        from saipen_engine import convergence

        root = Path(tempfile.mkdtemp(prefix="r010_conv_defer_bad_"))
        try:
            source_id = _write_convergence_fixture(root)
            SP._locator_path(root, "crew_defer").write_text("{broken", encoding="utf-8")
            verdict = convergence.convergence_verdict(root, source_id=source_id)
            self.assertFalse(verdict.ok)
            self.assertTrue(any("corruption" in r for r in verdict.reasons), verdict.reasons)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
