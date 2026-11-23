"""T-1516: durable receipts keep their verdict at any path.

T-1514 moved LOG and BOARD details onto the lineage. Four more stores still
demanded that a record's `project_identity` -- the machine-local realpath that
`paths.project_identity` documents as never durable -- match the live checkout:
debt baselines, RV re-verification receipts (validator closure evidence), EX
external-resolution receipts (closure evidence) and accepted legacy debt (the
validator's downgrade of sealed `[saio]` findings). A copy or a move of the
project therefore turned verified closures and accepted debt back into FAILs.
Each store now binds the lineage; a foreign lineage still refuses, and a
lineage-less project stays bound to its path.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import accepted_debt as accepted_mod  # noqa: E402
from saipen_engine import debt as debt_mod  # noqa: E402
from saipen_engine import external as external_mod  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.paths import (  # noqa: E402
    IDENTITY_NAME,
    SAIPEN_DIR,
    identity_file_content,
    new_project_lineage,
    project_identity,
    project_lineage_identity,
)
from test_accepted_debt import Fixture as AcceptedDebtFixture  # noqa: E402
from test_external_resolution import RUN_OK, _make_project, _resolve_args, _run_cli  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_reverify import ReverifyFixture  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def copy_elsewhere(case: unittest.TestCase, project: Path) -> Path:
    base = Path(tempfile.mkdtemp(prefix="saipen-t1516-copy-"))
    case.addCleanup(shutil.rmtree, base, ignore_errors=True)
    target = base / "moved" / "project"
    shutil.copytree(project, target)
    case.assertNotEqual(project_identity(target), project_identity(project))
    return target


def another_lineage(project: Path) -> None:
    """Make ``project`` a genuinely different project: its own lineage."""
    (project / SAIPEN_DIR / IDENTITY_NAME).write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )


class BaselineAndReverifyTests(ReverifyFixture):
    def reverified(self) -> str:
        with patch.object(debt_mod, "capture_findings", return_value=self._canned([])):
            result = debt_mod.reverify_work(self.root, "T-001", "probe", runs=["exit 0"])
        self.assertTrue(result["ok"], result)
        return result["receipt_id"]

    def test_a_baseline_loads_in_a_copy_at_another_path(self):
        created = debt_mod.create_snapshot(self.root, "probe", "baseline capture")
        self.assertTrue(created["ok"], created)
        moved = copy_elsewhere(self, self.root)
        record = debt_mod.load_snapshot(moved, created["snapshot_id"])
        self.assertEqual(record["snapshot_id"], created["snapshot_id"])

    def test_a_baseline_never_crosses_lineages(self):
        created = debt_mod.create_snapshot(self.root, "probe", "baseline capture")
        self.assertTrue(created["ok"], created)
        moved = copy_elsewhere(self, self.root)
        another_lineage(moved)
        with self.assertRaises(debt_mod.DebtRefusal) as caught:
            debt_mod.load_snapshot(moved, created["snapshot_id"])
        self.assertEqual(caught.exception.code, "DEBT_SNAPSHOT_FOREIGN_LINEAGE")

    def test_a_reverify_pass_stays_closure_evidence_in_a_copy(self):
        # current_tree_reverify is the validator's closure-evidence path.
        receipt_id = self.reverified()
        moved = copy_elsewhere(self, self.root)
        found = debt_mod.current_tree_reverify(moved, "T-001")
        self.assertIsNotNone(found)
        self.assertEqual(found["receipt_id"], receipt_id)

    def test_a_reverify_pass_never_crosses_lineages(self):
        receipt_id = self.reverified()
        moved = copy_elsewhere(self, self.root)
        another_lineage(moved)
        with self.assertRaises(debt_mod.DebtRefusal) as caught:
            debt_mod.load_reverify_receipt(moved, receipt_id)
        self.assertEqual(caught.exception.code, "REVERIFY_RECEIPT_FOREIGN_LINEAGE")
        self.assertIsNone(debt_mod.latest_pass_reverify(moved, "T-001"))

    def test_a_lineage_less_project_keeps_its_path_binding(self):
        receipt_id = self.reverified()
        moved = copy_elsewhere(self, self.root)
        (moved / SAIPEN_DIR / IDENTITY_NAME).unlink()
        path = moved / debt_mod.REVERIFY_DIR / f"{receipt_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["project_lineage"] = None
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        self.assertIsNone(project_lineage_identity(moved))
        self.assertIsNone(debt_mod.latest_pass_reverify(moved, "T-001"))


class ExternalResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="saipen-t1516-external-")
        self.addCleanup(tmp.cleanup)
        self.root = _make_project(Path(tmp.name))
        rc, payload, out = _run_cli(self.root, *_resolve_args("--run", RUN_OK))
        self.assertEqual(rc, 0, out)
        self.assertEqual(payload.get("code"), "EXTERNAL_RESOLVED", out)

    @staticmethod
    def problems(project: Path) -> list[str]:
        board = parse_board((project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
        return external_mod.resolution_problems(project, "T-030", board["tickets"]["T-030"])

    def test_the_resolution_holds_in_place(self):
        self.assertEqual(self.problems(self.root), [])

    def test_the_resolution_holds_in_a_copy_at_another_path(self):
        self.assertEqual(self.problems(copy_elsewhere(self, self.root)), [])

    def test_a_resolution_never_crosses_lineages(self):
        moved = copy_elsewhere(self, self.root)
        another_lineage(moved)
        problems = self.problems(moved)
        self.assertTrue(any("different project lineage" in p for p in problems), problems)


class AcceptedDebtTests(AcceptedDebtFixture):
    def test_the_acceptance_holds_in_a_copy_at_another_path(self):
        self.register_json(["E-003", "E-004"])
        self.root = copy_elsewhere(self, self.root)
        done = self.run_validator()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("WARN [accepted-legacy-debt]:", done.stdout)
        self.assertEqual(self.provenance_fail_lines(done.stdout), [])

    def test_an_acceptance_never_crosses_lineages(self):
        record_id = self.register_json(["E-003", "E-004"])["record_id"]
        self.root = copy_elsewhere(self, self.root)
        another_lineage(self.root)
        with self.assertRaises(accepted_mod.AcceptedDebtRefusal) as caught:
            accepted_mod.load_record(self.root, record_id)
        self.assertEqual(caught.exception.code, "ACCEPTED_DEBT_FOREIGN_LINEAGE")


if __name__ == "__main__":
    unittest.main()
