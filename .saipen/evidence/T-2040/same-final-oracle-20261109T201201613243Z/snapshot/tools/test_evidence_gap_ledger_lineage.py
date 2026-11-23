"""Independent red controls for the evidence-gap ledger provider (SRC-380).

Five reproduced correctness defects in
`tools/saipen_engine/discovery_providers.py::EvidenceGapLedgerProvider.evaluate`:

P0-01 the satisfied early-return runs BEFORE capture/patch lineage validation, so
      a ledger that reports total=described and omits the mandatory capture SHA
      and patch identity still answers SATISFIED;
P0-02 a required patch is only compared when the ledger happens to supply one,
      so an absent identity bypasses the mismatch conditional;
P1-03 a positive unresolved count with an empty/partial enumeration reports
      completeness COMPLETE and zero work instead of incomplete inventory;
P1-04 the candidate fingerprint is the hash of the ENTIRE ledger, so an
      unrelated ledger update reopens every unchanged DONE item;
P0-05 metrics.independently_verified aliases the described count, so purely
      documentary coverage reads as independently verified.

Every control here fails on the pre-fix subject and passes on the fix.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.discovery_providers import (  # noqa: E402
    COMPLETION_FULL,
    COMPLETION_PARTIAL,
    EvidenceGapLedgerProvider,
)
from saipen_engine.persistent_goal import (  # noqa: E402
    STATUS_ACTIONABLE_GAPS,
    STATUS_BLOCKED_BY_EVIDENCE,
    STATUS_DISCOVERY_REQUIRED,
    STATUS_NO_ADMISSIBLE_WORK,
    STATUS_SATISFIED,
    PersistentGoal,
    save_goal,
)
from saipen_engine.replenishment import replenish_from_goals  # noqa: E402


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EvidenceGapLedgerLineageTests(unittest.TestCase):
    """P0-01..P0-05 controls for EvidenceGapLedgerProvider."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saipen_gap_lineage_")).resolve()
        self.saipen_dir = self.tmp / ".saipen"
        (self.saipen_dir / "goals").mkdir(parents=True, exist_ok=True)
        (self.saipen_dir / "evidence").mkdir(parents=True, exist_ok=True)
        (self.saipen_dir / "BOARD.md").write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n",
            encoding="utf-8",
        )
        self.ledger_rel = ".saipen/evidence/coverage.json"
        self.ledger_path = self.tmp / self.ledger_rel
        self.provider = EvidenceGapLedgerProvider()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    # Helpers -------------------------------------------------------------

    def _write_ledger(self, data: dict) -> None:
        self.ledger_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _goal(self, **success_criteria) -> PersistentGoal:
        return PersistentGoal(
            goal_id="G-LIN",
            project_id="_BZ_REA",
            title="Semantics",
            objective="Reverse engineer procedure semantics",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=self.ledger_rel,
            success_criteria=dict(success_criteria),
        )

    def _capture_bytes(self, blob: bytes = b"BZCC-2.0.185-CAPTURE") -> str:
        (self.tmp / "capture.bin").write_bytes(blob)
        return hashlib.sha256(blob).hexdigest()

    # P0-01: captured lineage is mandatory before any SATISFIED -------------

    def test_p0_01_missing_capture_cannot_satisfy(self) -> None:
        """total=described, zero gaps, mandatory capture SHA absent -> not SATISFIED."""
        self._write_ledger({"counts": {"procedures": 10, "described_procedures": 10, "gap_procedures": 0}})
        goal = self._goal(capture_sha256="a" * 64, target_patch="public-2.0.185")
        ev = self.provider.evaluate(self.tmp, goal)
        self.assertNotEqual(ev.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(ev.satisfaction_status, STATUS_BLOCKED_BY_EVIDENCE)
        self.assertTrue(any("capture" in b.lower() for b in ev.blockers), ev.blockers)

    def test_p0_01_wrong_capture_cannot_satisfy(self) -> None:
        self._write_ledger(
            {
                "counts": {"procedures": 10, "described_procedures": 10, "gap_procedures": 0},
                "sources": {"capture": {"sha256": "b" * 64, "path": "capture.bin"}},
            }
        )
        goal = self._goal(capture_sha256="a" * 64, target_patch="public-2.0.185")
        ev = self.provider.evaluate(self.tmp, goal)
        self.assertNotEqual(ev.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(ev.satisfaction_status, STATUS_BLOCKED_BY_EVIDENCE)

    def test_p0_01_self_reported_capture_cannot_satisfy(self) -> None:
        """A SHA nothing can verify is not authenticated provenance."""
        self._write_ledger(
            {
                "counts": {"procedures": 10, "described_procedures": 10, "gap_procedures": 0},
                "sources": {"capture": {"sha256": "c" * 64, "path": "missing-capture.bin"}},
            }
        )
        goal = self._goal(capture_sha256="c" * 64, target_patch="public-2.0.185")
        ev = self.provider.evaluate(self.tmp, goal)
        self.assertNotEqual(ev.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(ev.satisfaction_status, STATUS_BLOCKED_BY_EVIDENCE)

    def test_p0_01_verified_capture_may_satisfy(self) -> None:
        """The positive control: bytes on disk derive the declared digest."""
        full = self._capture_bytes()
        self._write_ledger(
            {
                "counts": {"procedures": 10, "described_procedures": 10, "gap_procedures": 0},
                "sources": {"capture": {"sha256": full, "path": "capture.bin", "patch": "public-2.0.185"}},
            }
        )
        goal = self._goal(capture_sha256=full, target_patch="public-2.0.185")
        ev = self.provider.evaluate(self.tmp, goal)
        self.assertEqual(ev.satisfaction_status, STATUS_SATISFIED, ev.blockers)
        self.assertEqual(ev.metrics["capture_provenance"], "VERIFIED")

    # P0-02: a required patch identity is verified, never optional ----------

    def test_p0_02_absent_required_patch_cannot_produce_actionable_work(self) -> None:
        self._write_ledger(
            {
                "counts": {"procedures": 100, "described_procedures": 10, "gap_procedures": 90},
                "sources": {"capture": {"sha256": "d" * 64, "path": "capture.bin"}},
                "gap": [{"rva": "0x1", "name": "FUN_1", "bytes": 40}],
            }
        )
        goal = self._goal(target_patch="public-2.0.185")
        ev = self.provider.evaluate(self.tmp, goal)
        self.assertEqual(ev.satisfaction_status, STATUS_BLOCKED_BY_EVIDENCE)
        self.assertEqual(ev.actionable_candidates, [])
        self.assertTrue(any("patch" in b.lower() for b in ev.blockers), ev.blockers)

    def test_p0_02_wrong_patch_cannot_produce_actionable_work(self) -> None:
        self._write_ledger(
            {
                "counts": {"procedures": 100, "described_procedures": 10, "gap_procedures": 90},
                "sources": {"capture": {"sha256": "d" * 64, "path": "capture.bin", "patch": "public-2.0.206"}},
                "gap": [{"rva": "0x1", "name": "FUN_1", "bytes": 40}],
            }
        )
        goal = self._goal(target_patch="public-2.0.185")
        ev = self.provider.evaluate(self.tmp, goal)
        self.assertEqual(ev.satisfaction_status, STATUS_BLOCKED_BY_EVIDENCE)
        self.assertEqual(ev.actionable_candidates, [])

    def test_p0_02_correct_patch_still_produces_candidates(self) -> None:
        self._write_ledger(
            {
                "counts": {"procedures": 100, "described_procedures": 10, "gap_procedures": 90},
                "sources": {"capture": {"sha256": "d" * 64, "path": "capture.bin", "patch": "public-2.0.185"}},
                "gap": [{"rva": "0x1", "name": "FUN_1", "bytes": 40}],
            }
        )
        goal = self._goal(target_patch="public-2.0.185")
        ev = self.provider.evaluate(self.tmp, goal)
        self.assertEqual(ev.satisfaction_status, STATUS_ACTIONABLE_GAPS)
        self.assertEqual(len(ev.actionable_candidates), 1)

    # P1-03: a partial enumeration is incomplete inventory ---------------

    def test_p1_03_positive_unresolved_with_empty_enumeration_is_incomplete(self) -> None:
        self._write_ledger({"counts": {"procedures": 10, "described_procedures": 1, "gap_procedures": 9}, "gap": []})
        goal = self._goal()
        ev = self.provider.evaluate(self.tmp, goal)
        self.assertNotEqual(ev.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(ev.satisfaction_status, STATUS_DISCOVERY_REQUIRED)
        self.assertNotEqual(ev.completeness_status, COMPLETION_FULL)
        self.assertEqual(ev.metrics["unresolved"], 9)
        self.assertEqual(ev.metrics["enumerated"], 0)
        self.assertTrue(any("enumerat" in b.lower() or "inventor" in b.lower() for b in ev.blockers), ev.blockers)

    def test_p1_03_complete_enumeration_reports_partial_not_required(self) -> None:
        self._write_ledger(
            {
                "counts": {"procedures": 3, "described_procedures": 1, "gap_procedures": 2},
                "gap": [{"rva": "0x1", "name": "FUN_1"}, {"rva": "0x2", "name": "FUN_2"}],
            }
        )
        ev = self.provider.evaluate(self.tmp, self._goal())
        self.assertEqual(ev.satisfaction_status, STATUS_ACTIONABLE_GAPS)
        self.assertEqual(ev.completeness_status, COMPLETION_PARTIAL)
        self.assertEqual(ev.metrics["enumerated"], 2)

    def test_p1_03_truncated_producer_pagination_is_reported(self) -> None:
        self._write_ledger(
            {
                "counts": {"procedures": 100, "described_procedures": 1, "gap_procedures": 99},
                "gap": [{"rva": "0x1", "name": "FUN_1"}],
                "page": {"complete": False, "next_cursor": "page-2"},
            }
        )
        ev = self.provider.evaluate(self.tmp, self._goal())
        self.assertEqual(ev.completeness_status, "TRUNCATED")
        self.assertNotEqual(ev.satisfaction_status, STATUS_SATISFIED)
        self.assertTrue(any("page-2" in b for b in ev.blockers), ev.blockers)

    # P1-04: item identity, not the whole-ledger digest --------------------

    def _two_item_ledger(self, extra_note: str, first_bytes: int = 40) -> None:
        self._write_ledger(
            {
                "counts": {"procedures": 4, "described_procedures": 2, "gap_procedures": 2},
                "generated_at": extra_note,
                "gap": [
                    {"rva": "0x1", "name": "FUN_1", "bytes": first_bytes},
                    {"rva": "0x2", "name": "FUN_2", "bytes": 80},
                ],
            }
        )

    def test_p1_04_fingerprint_is_stable_across_unrelated_ledger_change(self) -> None:
        self._two_item_ledger("gen-1")
        first = {c.candidate_id: c.evidence_fingerprint for c in self.provider.evaluate(self.tmp, self._goal()).actionable_candidates}
        self._two_item_ledger("gen-2")  # unrelated ledger-level change only
        second = {c.candidate_id: c.evidence_fingerprint for c in self.provider.evaluate(self.tmp, self._goal()).actionable_candidates}
        self.assertEqual(first, second)

    def test_p1_04_fingerprint_changes_when_the_item_itself_changes(self) -> None:
        self._two_item_ledger("gen-1", first_bytes=40)
        before = {c.candidate_id: c.evidence_fingerprint for c in self.provider.evaluate(self.tmp, self._goal()).actionable_candidates}
        self._two_item_ledger("gen-1", first_bytes=4111)
        after = {c.candidate_id: c.evidence_fingerprint for c in self.provider.evaluate(self.tmp, self._goal()).actionable_candidates}
        self.assertNotEqual(before["G-LIN-FUN_1"], after["G-LIN-FUN_1"])
        self.assertEqual(before["G-LIN-FUN_2"], after["G-LIN-FUN_2"])

    def test_p1_04_unrelated_change_does_not_reopen_done_item(self) -> None:
        """End to end: a DONE item stays suppressed after an unrelated ledger edit."""
        self._two_item_ledger("gen-1")
        goal = self._goal()
        save_goal(self.tmp, goal)
        cands = {c.candidate_id: c.evidence_fingerprint for c in self.provider.evaluate(self.tmp, goal).actionable_candidates}
        fp1 = cands["G-LIN-FUN_1"]
        (self.saipen_dir / "BOARD.md").write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n"
            f"- [x] T-11 [P2] Investigate semantics of FUN_1 \\| goal: G-LIN \\| candidate: G-LIN-FUN_1 \\| evidence_fp: {fp1}"
            f" | verify: fixture FUN_1 semantics verified at {fp1}\n"
            "\n## BLOCKED\n",
            encoding="utf-8",
        )
        self._two_item_ledger("gen-2")
        rep = replenish_from_goals(self.tmp, "test-agent", dry_run=True)
        self.assertTrue(rep["ok"])
        self.assertTrue(rep["replenished"])
        self.assertNotEqual(rep["candidate"]["candidate_id"], "G-LIN-FUN_1")
        self.assertEqual(rep["candidate"]["candidate_id"], "G-LIN-FUN_2")

    def test_p1_04_genuine_new_item_evidence_still_reopens(self) -> None:
        """Per-item bytes changed under the SAME ledger path is a new generation."""
        self._two_item_ledger("gen-1", first_bytes=40)
        goal = self._goal()
        save_goal(self.tmp, goal)
        cands = {c.candidate_id: c.evidence_fingerprint for c in self.provider.evaluate(self.tmp, goal).actionable_candidates}
        fp1 = cands["G-LIN-FUN_1"]
        (self.saipen_dir / "BOARD.md").write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n"
            f"- [x] T-11 [P2] Investigate semantics of FUN_1 \\| goal: G-LIN \\| candidate: G-LIN-FUN_1 \\| evidence_fp: {fp1}"
            f" | verify: fixture FUN_1 semantics verified at {fp1}\n"
            "\n## BLOCKED\n",
            encoding="utf-8",
        )
        self._two_item_ledger("gen-1", first_bytes=4111)
        rep = replenish_from_goals(self.tmp, "test-agent", dry_run=True)
        self.assertTrue(rep["ok"])
        self.assertTrue(rep["replenished"])
        self.assertEqual(rep["candidate"]["candidate_id"], "G-LIN-FUN_1")

    # P0-05: described is never independently verified ---------------------

    def test_p0_05_described_does_not_count_as_independently_verified(self) -> None:
        self._write_ledger(
            {
                "counts": {"procedures": 10, "described_procedures": 4, "gap_procedures": 6},
                "gap": [{"rva": "0x1", "name": "FUN_1"}],
            }
        )
        ev = self.provider.evaluate(self.tmp, self._goal())
        self.assertEqual(ev.metrics["semantically_described"], 4)
        self.assertEqual(ev.metrics["independently_verified"], 0)

    def test_p0_05_authoritative_independent_tier_is_carried_through(self) -> None:
        self._write_ledger(
            {
                "counts": {
                    "procedures": 10,
                    "described_procedures": 4,
                    "independently_verified_procedures": 3,
                    "gap_procedures": 6,
                },
                "gap": [{"rva": "0x1", "name": "FUN_1"}],
            }
        )
        ev = self.provider.evaluate(self.tmp, self._goal())
        self.assertEqual(ev.metrics["independently_verified"], 3)
        self.assertEqual(ev.metrics["semantically_described"], 4)

    def test_p0_05_documentation_count_alone_cannot_satisfy(self) -> None:
        self._write_ledger(
            {
                "counts": {
                    "procedures": 4,
                    "described_procedures": 4,
                    "independently_verified_procedures": 0,
                    "gap_procedures": 0,
                }
            }
        )
        goal = self._goal(require_independent_verification=True)
        ev = self.provider.evaluate(self.tmp, goal)
        self.assertNotEqual(ev.satisfaction_status, STATUS_SATISFIED)
        self.assertTrue(any("independent" in b.lower() for b in ev.blockers), ev.blockers)

    def test_unknown_provider_registry_is_unchanged(self) -> None:
        """Guard: this repair adds no provider and renames none."""
        from saipen_engine.discovery_providers import list_providers

        self.assertEqual(
            list_providers(),
            [
                "audit_inbox",
                "backlog",
                "comprehensive_maintenance",
                "evidence_gap_ledger",
                "failed_tests",
                "source_change",
            ],
        )


if __name__ == "__main__":
    unittest.main()
