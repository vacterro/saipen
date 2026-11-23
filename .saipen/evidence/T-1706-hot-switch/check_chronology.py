"""Run the proposed chronology oracle without editing the frozen source."""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))

suite = unittest.defaultTestLoader.discover(
    str(HERE / "draft"), pattern="test_t1707_regression_chronology.py",
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
