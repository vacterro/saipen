"""T-1298 REVIEW battery: the full discover set MINUS the excluded foreign
T-1301 test file (test_debt_gate.py). Kitchen helper, not a repo artifact."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
EXCLUDED = {"test_debt_gate.py"}

loader = unittest.TestLoader()
suite = unittest.TestSuite()
for path in sorted(TOOLS.glob("test_*.py")):
    if path.name in EXCLUDED:
        continue
    mod = f"tools.{path.stem}"
    __import__(mod)
    suite.addTests(loader.loadTestsFromName(mod))

runner = unittest.TextTestRunner(verbosity=1)
result = runner.run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
