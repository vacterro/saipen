"""Closed-source success must describe and prove the actual archive outcome."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import intake
from test_hermetic_env import hermetic_env, isolate_host_session
import test_source_receipts as receipt_fixtures


def setUpModule():
    isolate_host_session()


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


class ClosureOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = receipt_fixtures.SourceReceiptTests(
            "test_src15_close_archives_and_removes_hot_body")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.receipt = self.fixture.capture("source outcome regression")["receipt"]
        self.fixture.normalized(self.receipt)
        self.fixture.resolve(self.receipt)

    def close(self):
        return intake.close_receipt(self.root, self.receipt, closure_event="E-9")

    def archive(self, suffix):
        return self.root / f".saipen/archive/source/{self.receipt}.{suffix}"

    def closed(self):
        result = self.close()
        self.assertTrue(result["ok"], result)
        self.assertEqual(intake.validate_project(self.root), [])
        return result

    def assert_corrupt_unchanged(self):
        before = tree_bytes(self.root)
        result = self.close()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "SOURCE_CORRUPTION", result)
        self.assertEqual(tree_bytes(self.root), before)

    def test_healthy_repeat_is_verified_already_closed_and_changes_nothing(self):
        self.closed()
        before = tree_bytes(self.root)
        result = self.close()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result.get("outcome"), "ALREADY_CLOSED", result)
        self.assertIs(result.get("archive_verified"), True)
        self.assertIs(result.get("recovered"), False)
        self.assertIs(result.get("residue_removed"), False)
        self.assertEqual(tree_bytes(self.root), before)

    def test_missing_metadata_refuses_without_writes(self):
        self.closed()
        self.archive("meta.json").unlink()
        self.assert_corrupt_unchanged()

    def test_missing_contract_refuses_without_writes(self):
        self.closed()
        self.archive("contract.json").unlink()
        self.assert_corrupt_unchanged()

    def test_missing_coverage_refuses_without_writes(self):
        self.closed()
        self.archive("coverage.json").unlink()
        self.assert_corrupt_unchanged()

    def test_missing_body_still_refuses_without_writes(self):
        self.closed()
        self.archive("md").unlink()
        self.assert_corrupt_unchanged()

    def test_malformed_metadata_refuses_without_writes(self):
        self.closed()
        self.archive("meta.json").write_text("[]", encoding="utf-8")
        self.assert_corrupt_unchanged()

    def test_weakened_archived_coverage_refuses_without_writes(self):
        self.closed()
        path = self.archive("coverage.json")
        coverage = json.loads(path.read_text(encoding="utf-8"))
        coverage["requirements"][f"{self.receipt}:R001"]["disposition"] = "UNKNOWN"
        path.write_text(json.dumps(coverage), encoding="utf-8")
        self.assert_corrupt_unchanged()

    def test_real_residue_cleanup_is_distinct_from_archive_repair(self):
        self.closed()
        active = self.root / f".saipen/intake/active/{self.receipt}.md"
        active.write_bytes(self.archive("md").read_bytes())
        archived = self.archive("md").read_bytes()
        log = (self.root / ".saipen/LOG.md").read_bytes()
        result = self.close()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result.get("outcome"), "RESIDUE_SETTLED", result)
        self.assertIs(result.get("archive_verified"), True)
        self.assertIs(result.get("recovered"), True)
        self.assertIs(result.get("residue_removed"), True)
        self.assertFalse(active.exists())
        self.assertEqual(self.archive("md").read_bytes(), archived)
        self.assertEqual((self.root / ".saipen/LOG.md").read_bytes(), log)
        self.assertEqual(intake.validate_project(self.root), [])

    def test_corrupt_archive_preserves_active_residue_for_recovery(self):
        self.closed()
        active = self.root / f".saipen/intake/active/{self.receipt}.md"
        active.write_bytes(self.archive("md").read_bytes())
        self.archive("contract.json").unlink()
        self.assert_corrupt_unchanged()

    def test_actual_interrupted_close_settlement_reports_repair(self):
        with mock.patch.object(intake, "_write_tombstone", side_effect=OSError("crash control")):
            interrupted = self.close()
        self.assertFalse(interrupted["ok"], interrupted)
        result = self.close()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result.get("outcome"), "REPAIR_APPLIED", result)
        self.assertIs(result.get("archive_verified"), True)
        self.assertEqual(intake.validate_project(self.root), [])
        before = tree_bytes(self.root)
        repeated = self.close()
        self.assertEqual(repeated.get("outcome"), "ALREADY_CLOSED", repeated)
        self.assertEqual(tree_bytes(self.root), before)

    def test_public_cli_refuses_the_same_missing_sidecar(self):
        self.closed()
        self.archive("meta.json").unlink()
        before = tree_bytes(self.root)
        cli = Path(intake.__file__).resolve().parents[1] / "saipen.py"
        result = subprocess.run(
            [sys.executable, "-B", str(cli), "source", "close", self.receipt,
             "--project-root", str(self.root), "--json"],
            capture_output=True, text=True, encoding="utf-8", env=hermetic_env(), timeout=60)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"], payload)
        self.assertEqual(payload["code"], "SOURCE_CORRUPTION")
        self.assertEqual(tree_bytes(self.root), before)


if __name__ == "__main__":
    unittest.main()
