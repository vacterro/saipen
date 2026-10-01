"""T-354: coverage for a source that was RETIRED under different Work.

`work_closure_gate` used to accept a tombstoned source only when the ticket
being gated was the very ticket that retired it (`work in tomb["linked_work(s)"]`).
That is a provenance-IDENTITY question, not the question the gate asks -- which
is whether every source a ticket cites is real and SETTLED. A request that
closes once its own clause ticket is DONE, while later findings raised under it
are still real Work, is the ordinary shape, and the identity test stranded those
findings in BLOCKED forever: `ticket done` refused with SOURCE_RECEIPT_MISSING,
`resolve-external` had no applicable reason class, `repair-metadata` was
DONE-rows-only, and supersession refused outright (T-250 / SRC-007, measured).

What this pins:

  1. GREEN  a tombstone that is CLOSED with unresolved 0 satisfies coverage for
            a citing ticket that is NOT its linked work -- the fix.
  2. RED    a tombstone that is CLOSED but still has an unresolved clause does
            NOT: settlement is what the gate measures, and dropping the
            identity test must not have dropped that.
  3. RED    a tombstone that is not CLOSED does NOT.
  4. RED    a cited receipt with no record at all does NOT.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from saipen_engine import intake  # noqa: E402

BOARD_TEMPLATE = (
    "# Board\n"
    "\n"
    "## DOING\n"
    "\n"
    "## TODO\n"
    "\n"
    "## DONE\n"
    "- [x] {work} [P1] fixture ticket | source_receipts: {receipt} | owner: test\n"
    "\n"
    "## BLOCKED\n"
)


def write_index(root: Path, tombstones: dict) -> None:
    (root / ".saipen/intake").mkdir(parents=True, exist_ok=True)
    (root / ".saipen/intake/index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "next_id": 900,
                "active": {},
                "tombstones": tombstones,
            }
        ),
        encoding="utf-8",
    )


def write_board(root: Path, work: str, receipt: str) -> None:
    (root / ".saipen").mkdir(parents=True, exist_ok=True)
    (root / ".saipen/BOARD.md").write_text(
        BOARD_TEMPLATE.format(work=work, receipt=receipt), encoding="utf-8"
    )


def settled_tombstone(linked_work: str, unresolved: int = 0, status: str = "CLOSED") -> dict:
    return {
        "schema_version": 1,
        "receipt_id": "SRC-777",
        "source_sha256": "a" * 64,
        "status": status,
        "linked_work": linked_work,
        "requirements": 15,
        "actionable": 15,
        "unresolved": unresolved,
    }


class RetiredSourceCoverage(unittest.TestCase):
    def _project(self, tomb: dict | None) -> tuple[str, Path]:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        work = "T-900"
        write_board(root, work, "SRC-777")
        write_index(root, {"SRC-777": tomb} if tomb is not None else {})
        return work, root

    def test_retired_under_other_work_satisfies_coverage(self):
        # The defect: this source was closed by T-800, and T-900 merely cites it.
        work, root = self._project(settled_tombstone("T-800"))
        result = intake.work_closure_gate(root, work)
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(result.get("code"), "SOURCE_COVERAGE_COMPLETE")

    def test_retired_with_unresolved_clause_still_refuses(self):
        work, root = self._project(settled_tombstone("T-800", unresolved=2))
        result = intake.work_closure_gate(root, work)
        self.assertFalse(result.get("ok"), "a tombstone with an open clause must refuse")
        self.assertNotEqual(result.get("code"), "SOURCE_COVERAGE_COMPLETE")

    def test_tombstone_not_closed_still_refuses(self):
        work, root = self._project(settled_tombstone("T-800", status="QUARANTINED"))
        result = intake.work_closure_gate(root, work)
        self.assertFalse(result.get("ok"), "only a CLOSED tombstone is coverage")
        self.assertNotEqual(result.get("code"), "SOURCE_COVERAGE_COMPLETE")

    def test_absent_receipt_still_refuses(self):
        work, root = self._project(None)
        result = intake.work_closure_gate(root, work)
        # No record at all must refuse. Which refusal code it lands on is the
        # refusal helper's business, not this contract's -- what matters is that
        # the retired-source relaxation cannot manufacture coverage for a receipt
        # that was never retired.
        self.assertFalse(result.get("ok"), "a cited receipt with no record must refuse")
        self.assertNotEqual(result.get("code"), "SOURCE_COVERAGE_COMPLETE")


if __name__ == "__main__":
    unittest.main()
