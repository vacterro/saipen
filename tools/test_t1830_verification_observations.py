"""Observed verification stages and exact shard membership, without a full run."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402
from saipen_engine.test_runner import TestFamily, _ignore_copy  # noqa: E402
from test_t1472_core_unit_shards import _shard  # noqa: E402


def shard(indices, digest="a" * 64):
    return _shard(manifest={"discovered": 4, "selected": len(indices), "modules": {},
                            "inventory_sha256": digest, "selected_indices": indices})


class ExactMembershipTests(unittest.TestCase):
    def test_legacy_discovery_cost_is_unknown_not_zero(self):
        self.assertIsNone(core_unit.merge_shards([_shard(), _shard()])["discovery_process_s"])

    def test_equal_counts_cannot_hide_a_duplicate_and_an_omission(self):
        merged = core_unit.merge_shards([shard([0, 1]), shard([1, 2])])
        self.assertIsNotNone(merged["partition_error"])

    def test_equal_counts_with_different_test_inventory_refuse(self):
        merged = core_unit.merge_shards([shard([0, 1]), shard([2, 3], "b" * 64)])
        self.assertIsNotNone(merged["partition_error"])

    def test_every_occurrence_exactly_once_passes(self):
        merged = core_unit.merge_shards([shard([0, 2]), shard([1, 3])])
        self.assertIsNone(merged["partition_error"])
        self.assertEqual(merged["membership_proof"]["inventory_sha256"], "a" * 64)

    def test_missing_or_invalid_membership_fails_closed(self):
        for bad in ([-1, 3], [True, 3], [2, 4], [2, 2]):
            with self.subTest(indices=bad):
                self.assertIsNotNone(
                    core_unit.merge_shards([shard([0, 1]), shard(bad)])["partition_error"]
                )
        legacy = _shard()
        legacy["membership_required"] = True
        self.assertIsNotNone(core_unit.merge_shards([legacy, legacy])["partition_error"])


class RealObservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = Path(tempfile.mkdtemp(prefix="t1830-"))
        self.addCleanup(core_unit.reclaim, self.temporary)
        self.project = self.temporary / "source"
        (self.project / "tools").mkdir(parents=True)
        for name in ("alpha", "beta"):
            (self.project / "tools" / f"test_{name}.py").write_text(
                "import unittest\nclass Test(unittest.TestCase):\n"
                "    def test_ok(self):\n        self.assertTrue(True)\n", encoding="utf-8"
            )
        self.family = TestFamily("unit", (sys.executable, "-B", "-m", "unittest", "discover",
                                          "-s", "tools", "-p", "test_*.py", "-v"), 30,
                                 environment_tools=())

    def test_copy_reports_actual_phases_and_preserves_all_bytes(self):
        state = self.project / ".saipen"
        (state / "evidence").mkdir(parents=True)
        (state / "STATE.md").write_text("state\n", encoding="utf-8")
        (state / "evidence/proof.json").write_text('{"proof":true}', encoding="utf-8")
        target = self.temporary / "copy"
        observed = core_unit.copy_tree_consistent(self.project, target, _ignore_copy)
        self.assertEqual(observed["canonical_copy_attempts"], 1)
        self.assertGreaterEqual(observed["subject_copy_s"], 0)
        self.assertGreaterEqual(observed["canonical_copy_s"], 0)
        self.assertEqual((target / ".saipen/evidence/proof.json").read_bytes(),
                         (state / "evidence/proof.json").read_bytes())

    def test_actual_serial_and_sharded_runs_keep_verdict_and_timing_scope(self):
        with mock.patch.object(core_unit, "family", return_value=self.family):
            for jobs in (1, 2):
                with self.subTest(jobs=jobs):
                    result = core_unit.run_family(self.project, jobs=jobs)
                    self.assertEqual((result["ran"], result["status"]), (2, "PASS"))
                    self.assertGreaterEqual(result["timings_s"]["execution_wall_s"], 0)
                    self.assertGreaterEqual(result["timings_s"]["hash_wall_s"], 0)
                    self.assertGreaterEqual(result["timings_s"]["cleanup_wall_s"], 0)
                    if jobs == 2:
                        self.assertIsNotNone(result["membership_proof"])
                        self.assertGreaterEqual(result["discovery_process_s"], 0)

    def test_new_test_and_import_failure_stay_in_exact_inventory(self):
        (self.project / "tools/test_broken.py").write_text("this is not Python !!!\n")
        with mock.patch.object(core_unit, "family", return_value=self.family):
            result = core_unit.run_family(self.project, jobs=2)
        self.assertEqual(result["ran"], 3)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("unittest.loader._FailedTest.test_broken", result["red"])
        self.assertIsNone(result["partition_error"])


if __name__ == "__main__":
    unittest.main()
