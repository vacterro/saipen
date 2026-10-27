"""The real cleanup acceptance runs on bounded private input, never the live repo."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1505_core_unit_sandbox_reclaim as cleanup_cases  # noqa: E402


class CleanupFixtureCostTests(unittest.TestCase):
    def test_actual_fixture_is_private_and_keeps_the_unchanged_acceptance_probe(self):
        case = cleanup_cases.RunFamilyLeavesNothingTests("test_a_whole_run_leaves_no_sandbox")

        def inspect(source, *, jobs):
            source = Path(source).resolve()
            self.assertNotEqual(source, TOOLS.parent.resolve())
            self.assertFalse(source.is_relative_to(TOOLS.parent.resolve()))
            self.assertFalse((source / ".saipen/evidence").exists())
            self.assertFalse((source / ".git").exists())
            self.assertEqual((source / "tools/test_hermetic_env.py").read_bytes(),
                             (TOOLS / "test_hermetic_env.py").read_bytes())
            self.assertTrue((source / "tools/saipen_engine/paths.py").is_file())
            objects = source / ".saipen/kitchen/.git/objects/01"
            self.assertEqual({p.name for p in objects.iterdir()}, {"af3d38", "0caaad"})
            self.assertEqual(jobs, 1)
            return {"status": "PASS", "sandboxes_leaked": []}

        try:
            with mock.patch.object(cleanup_cases.core_unit, "run_family", side_effect=inspect):
                case.run_small(1)
        finally:
            case.doCleanups()


if __name__ == "__main__":
    unittest.main()
