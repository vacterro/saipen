"""T-2051: intake-index authority re-derived from archived bundles on disk."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from saipen_engine import source_reindex


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _bundle(root: Path, receipt_id: str, *, linked_work: str = "T-0001", clauses: int = 1) -> dict:
    """Write a byte-exact closed archived bundle the canonical reader accepts."""
    body = f"{receipt_id} body\n"
    digest = _digest(body)
    _write(root / ".saipen/archive/source" / f"{receipt_id}.md", body)
    clause_map = {
        f"{receipt_id}:R{index:03d}": {
            "actionable": True,
            "class": "requirement",
            "text": f"clause {index}",
        }
        for index in range(1, clauses + 1)
    }
    _write(
        root / ".saipen/archive/source" / f"{receipt_id}.contract.json",
        json.dumps(
            {
                "clauses": clause_map,
                "derived_at": "2026-11-12T10:00:00Z",
                "derived_from": f".saipen/archive/source/{receipt_id}.md",
                "interpretation_revision": 0,
                "schema_version": 1,
                "source_sha256": digest,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    _write(
        root / ".saipen/archive/source" / f"{receipt_id}.coverage.json",
        json.dumps(
            {
                "requirements": {
                    key: {
                        "actionable": True,
                        "class": "requirement",
                        "disposition": "VERIFIED",
                        "evidence": "T-0001 closed with verification evidence in LOG",
                        "text": clause_map[key]["text"],
                        "verification": "verify -> PASS [target: T-0001] conf: high",
                        "work": linked_work,
                    }
                    for key in clause_map
                },
                "schema_version": 1,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    _write(
        root / ".saipen/archive/source" / f"{receipt_id}.meta.json",
        json.dumps(
            {
                "archive_ref": f".saipen/archive/source/{receipt_id}.md",
                "closed_at": "2026-11-12T10:00:00Z",
                "closure_event": "E-00001",
                "linked_work": linked_work,
                "receipt_id": receipt_id,
                "received_at": "2026-11-11T10:00:00Z",
                "reread_at": "2026-11-12T10:00:00Z",
                "schema_version": 1,
                "source_kind": "user_instruction",
                "source_sha256": digest,
                "status": "CLOSED",
                "storage_status": "ARCHIVED",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return {"digest": digest, "body": body}


def _board(root: Path, rows: list[tuple[str, str]]) -> None:
    lines = ["# BOARD", "", "## TODO", ""]
    for ticket, receipts in rows:
        lines.append(f"- [ ] {ticket} [P2] work item | source_receipts: {receipts}")
    for heading in ("## DOING", "## DONE", "## BLOCKED"):
        lines.extend(["", heading, ""])
    _write(root / ".saipen/BOARD.md", "\n".join(lines).rstrip("\n") + "\n")


def _index(root: Path, *, active=None, tombstones=None) -> None:
    _write(
        root / ".saipen/intake/index.json",
        json.dumps(
            {
                "active": active or {},
                "next_id": 411,
                "schema_version": 1,
                "tombstones": tombstones or {},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


class PlanTests(unittest.TestCase):
    def test_recoverable_bundle_is_classified_with_a_derived_tombstone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _bundle(root, "SRC-385", linked_work="T-2015", clauses=2)
            _board(root, [("T-2015", "SRC-385")])
            _index(root)
            report = source_reindex.plan(root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["recoverable"], ["SRC-385"])
            entry = report["entries"][0]
            self.assertEqual(entry["state"], source_reindex.RECOVERABLE)
            self.assertEqual(entry["referenced_by"], ["T-2015"])
            tombstone = entry["tombstone"]
            self.assertEqual(tombstone["status"], "CLOSED")
            self.assertEqual(tombstone["requirements"], 2)
            self.assertEqual(tombstone["actionable"], 2)
            self.assertEqual(tombstone["unresolved"], 0)
            self.assertEqual(tombstone["source_sha256"], bundle["digest"])
            self.assertEqual(tombstone["linked_work"], "T-2015")

    def test_missing_carrier_is_no_evidence_with_the_exact_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _board(root, [("T-2042", "SRC-401")])
            _index(root)
            report = source_reindex.plan(root)
            self.assertEqual(report["recoverable"], [])
            self.assertEqual(report["no_evidence"], ["SRC-401"])
            entry = report["entries"][0]
            self.assertIsNone(entry["tombstone"])
            self.assertIn("SRC-401.meta.json", entry["missing_proof"])

    def test_a_known_receipt_is_not_a_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _board(root, [("T-2015", "SRC-001")])
            _index(root, active={"SRC-001": {"linked_work": "T-2015", "source_sha256": "0" * 64}})
            report = source_reindex.plan(root)
            self.assertEqual(report["entries"], [])
            self.assertEqual(report["code"], "NOTHING_TO_RECONCILE")

    def test_digest_drift_refuses_the_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _bundle(root, "SRC-385")
            _write(root / ".saipen/archive/source" / "SRC-385.md", "tampered\n")
            _board(root, [("T-2015", "SRC-385")])
            _index(root)
            entry = source_reindex.plan(root)["entries"][0]
            self.assertEqual(entry["state"], source_reindex.NO_EVIDENCE)
            self.assertIn("digest mismatch", entry["missing_proof"])
            self.assertNotEqual(bundle["digest"], "")

    def test_unresolved_coverage_refuses_the_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bundle(root, "SRC-385")
            coverage_path = root / ".saipen/archive/source" / "SRC-385.coverage.json"
            coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
            coverage["requirements"]["SRC-385:R001"] = {
                "actionable": True,
                "class": "requirement",
                "disposition": "OPEN",
                "evidence": None,
                "text": "clause 1",
                "verification": None,
                "work": "T-2015",
            }
            _write(coverage_path, json.dumps(coverage, indent=2, sort_keys=True) + "\n")
            _board(root, [("T-2015", "SRC-385")])
            _index(root)
            entry = source_reindex.plan(root)["entries"][0]
            self.assertEqual(entry["state"], source_reindex.NO_EVIDENCE)

    def test_duplicate_references_are_grouped_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bundle(root, "SRC-385", linked_work="T-2015")
            _board(root, [("T-2015", "SRC-385"), ("T-2016", "SRC-385")])
            _index(root)
            report = source_reindex.plan(root)
            self.assertEqual(len(report["entries"]), 1)
            self.assertEqual(report["entries"][0]["referenced_by"], ["T-2015", "T-2016"])

    def test_unreadable_index_is_refused_not_emptied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _board(root, [])
            _write(root / ".saipen/intake/index.json", "{nope")
            report = source_reindex.plan(root)
            self.assertFalse(report["ok"])
            self.assertIn("index", report["detail"])

    def test_plan_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bundle(root, "SRC-385")
            _board(root, [("T-2015", "SRC-385")])
            _index(root)
            before = (root / ".saipen/intake/index.json").read_bytes()
            source_reindex.plan(root)
            self.assertEqual(before, (root / ".saipen/intake/index.json").read_bytes())


class CarrierTests(unittest.TestCase):
    def test_carrier_state_reports_every_expected_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bundle(root, "SRC-385")
            state = source_reindex.carrier_state(root, "SRC-385")
            self.assertEqual(sorted(state), sorted(source_reindex.CARRIERS))
            self.assertTrue(all(state.values()))

    def test_missing_meta_is_named_precisely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as caught:
                source_reindex.derived_tombstone(Path(tmp), "SRC-999")
            self.assertIn("SRC-999.meta.json", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
