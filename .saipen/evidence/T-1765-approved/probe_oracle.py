"""Run the proposed frozen oracle without editing the product/test tree."""
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
suite = unittest.defaultTestLoader.discover(
    str(Path(__file__).resolve().parent), pattern="test_t1765_finding_subtypes.py",
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
