"""audit/20 W2-001, W2-002, W2-003 -- the source-receipt writer boundary.

Three findings, one file. All three are refusals that looked successful:

W2-001 `purge_receipt` was the only public mutator with no `project_writer_lock`,
       so two writers could delete through each other's critical section.
W2-002 `_commit_source_link` rolled back only BOARD, leaving the compaction
       detail files and the durable metadata describing a link nobody committed.
W2-003 a blanket `except (OSError, PermissionError, ValueError)` flattened the
       lock's own `WRITER_BUSY` into `VALIDATION_FAILED`, so a busy lock read as
       a malformed receipt.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import intake  # noqa: E402
from saipen_engine.lock import project_writer_lock  # noqa: E402

SCENARIO = ROOT / "tests" / "scenarios" / "stale-state-reconciliation" / ".saipen"


class _Project(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1544-intake-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        self.config = Path(self.tmp.name) / "user-config"
        self.env = patch.dict(os.environ, {"SAIPEN_USER_CONFIG_HOME": str(self.config)})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def closed_receipt(self) -> str:
        receipt = intake.capture(
            self.root, "authoritative\r\nsource\nΩ", source_kind="user_audit"
        )["receipt"]
        intake.add_requirement(self.root, receipt, rid="R001", text="Requirement 1")
        intake.set_disposition(
            self.root, receipt, "R001", "VERIFIED", evidence="E-1", verification="t-1:PASS"
        )
        self.assertTrue(intake.close_receipt(self.root, receipt)["ok"])
        return receipt


class WriterBusyClassificationTests(_Project):
    """W2-003: contention keeps its own code; real IO failure does not."""

    def _busy(self, call) -> dict:
        with project_writer_lock(self.root):
            return call()

    def test_a_busy_lock_is_not_a_malformed_receipt(self) -> None:
        receipt = intake.capture(self.root, "body", source_kind="user_audit")["receipt"]
        intake.add_requirement(self.root, receipt, rid="R001", text="Requirement 1")
        cases = {
            "set_disposition": lambda: intake.set_disposition(
                self.root, receipt, "R001", "VERIFIED", evidence="E-1", verification="t-1:PASS"
            ),
            "capture": lambda: intake.capture(self.root, "second", source_kind="user_audit"),
            "archive_receipt": lambda: intake.archive_receipt(self.root, receipt),
            "purge_receipt": lambda: intake.purge_receipt(self.root, receipt),
        }
        for name, call in cases.items():
            with self.subTest(mutator=name):
                result = self._busy(call)
                self.assertFalse(result["ok"], name)
                self.assertEqual(result["code"], "WRITER_BUSY", name)

    def test_an_unrelated_permission_error_is_still_a_validation_failure(self) -> None:
        # Only the lock's own signal is reclassified. A file that cannot be read
        # is still a validation failure, not a retry hint.
        with patch.object(intake, "_read_index", side_effect=PermissionError("EACCES")):
            result = intake.capture(self.root, "body", source_kind="user_audit")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_a_busy_lock_writes_nothing(self) -> None:
        intake.capture(self.root, "body", source_kind="user_audit")
        index = self.root / ".saipen/intake/index.json"
        before = index.read_bytes()
        with project_writer_lock(self.root):
            intake.capture(self.root, "second", source_kind="user_audit")
        self.assertEqual(index.read_bytes(), before)


class PurgeSerializationTests(_Project):
    """W2-001: the destructive mutator serializes like every other one."""

    def test_purge_refuses_while_another_writer_holds_the_lock(self) -> None:
        receipt = self.closed_receipt()
        self.assertTrue((self.root / f".saipen/archive/source/{receipt}.md").is_file())
        tomb = (self.root / f".saipen/intake/tombstones/{receipt}.json").read_bytes()
        index = (self.root / ".saipen/intake/index.json").read_bytes()
        with project_writer_lock(self.root):
            result = intake.purge_receipt(self.root, receipt)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "WRITER_BUSY")
        self.assertTrue((self.root / f".saipen/archive/source/{receipt}.md").is_file())
        self.assertEqual(
            (self.root / f".saipen/intake/tombstones/{receipt}.json").read_bytes(), tomb
        )
        self.assertEqual((self.root / ".saipen/intake/index.json").read_bytes(), index)

    def test_purge_still_succeeds_with_no_contention(self) -> None:
        receipt = self.closed_receipt()
        self.assertTrue(intake.purge_receipt(self.root, receipt)["ok"])
        self.assertEqual(intake.status(self.root, receipt)["location"], "purged")


class LinkageRollbackTests(_Project):
    """W2-002: a refused linkage leaves every authority unlinked."""

    def _inject_index_failure(self):
        real = intake._write_index

        def boom(root, index):
            raise OSError("INJECT_INDEX_FAIL_LINK")

        return patch.object(intake, "_write_index", boom), real

    def test_a_failure_between_metadata_and_index_unlinks_every_authority(self) -> None:
        receipt = intake.capture(self.root, "body", source_kind="user_audit")["receipt"]
        board = self.root / ".saipen/BOARD.md"
        index = self.root / ".saipen/intake/index.json"
        meta = self.root / f".saipen/intake/active/{receipt}.meta.json"
        board_before = board.read_bytes()
        fault, _ = self._inject_index_failure()
        with fault:
            result = intake.link_work_to(self.root, receipt, "T-001")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "ORPHAN_RECEIPT")
        # The audit's exact three-authority split: BOARD rolled back, metadata
        # durable, index not written. Before the fix the metadata kept the link.
        self.assertEqual(board.read_bytes(), board_before)
        entry = json.loads(index.read_text(encoding="utf-8"))["active"][receipt]
        self.assertIsNone(entry["linked_work"])
        self.assertEqual(json.loads(meta.read_text(encoding="utf-8")).get("linked_work"), None)

    def test_the_project_still_validates_after_a_refused_linkage(self) -> None:
        receipt = intake.capture(self.root, "body", source_kind="user_audit")["receipt"]
        fault, _ = self._inject_index_failure()
        with fault:
            intake.link_work_to(self.root, receipt, "T-001")
        self.assertEqual(intake.validate_project(self.root), [])

    def test_the_linkage_commits_when_nothing_fails(self) -> None:
        receipt = intake.capture(self.root, "body", source_kind="user_audit")["receipt"]
        self.assertTrue(intake.link_work_to(self.root, receipt, "T-001")["ok"])
        meta = json.loads(
            (self.root / f".saipen/intake/active/{receipt}.meta.json").read_text(encoding="utf-8")
        )
        self.assertEqual(meta["linked_work"], "T-001")
        self.assertEqual(intake.validate_project(self.root), [])


if __name__ == "__main__":
    unittest.main()
