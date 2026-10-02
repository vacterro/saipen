"""Run actor regressions with only the original actor-dropping seam restored."""
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import saipen
from saipen_engine import telegrams
import test_t1497_turn_entry_telegrams as tests


def original_seam(project_root, state):
    return telegrams.turn_entry(project_root, state)


with mock.patch.object(saipen, "_turn_entry_telegrams", original_seam):
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(tests.TelegramActorTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
