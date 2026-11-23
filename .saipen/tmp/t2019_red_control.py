"""Exercise the unchanged replay with the stop detector deliberately disabled."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd() / "tools"))
import test_t2019_suite_preflight as tests
from saipen_engine import test_runner

suite = unittest.TestSuite([
    tests.SuitePreflightTests("test_stub_mismatch_stops_before_sibling_and_reaps_descendants")
])
with patch.object(test_runner, "_failure_line", return_value=False):
    result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
