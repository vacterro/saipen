"""Run the unchanged F/G verifier against a bounded bad runtime resolution."""
import sys
import unittest
from pathlib import Path
from unittest import mock

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'tools'))
import saipen
from test_command_routing import RetiredShortcutMigrationTests

suite = unittest.TestSuite([RetiredShortcutMigrationTests(
    'test_instrumented_ss_reaches_neither_stop_nor_status_implementation'
)])
with mock.patch.object(saipen, 'resolve_shortcut', return_value='stop'):
    result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
