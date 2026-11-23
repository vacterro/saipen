"""Repository-discovery neighbors for the approved compatibility repair."""
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
patterns = [
    "test_t1765_finding_subtypes.py", "test_debt_gate.py", "test_reverify.py",
    "test_conformance_repair_boundary.py", "test_conformance_remediation_evidence.py",
]
loader = unittest.TestLoader()
suite = unittest.TestSuite(loader.discover(str(root / "tools"), pattern=pattern) for pattern in patterns)
with (Path(__file__).resolve().parent / "focused.txt").open("w", encoding="utf-8") as stream:
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
print(f"ran={result.testsRun} failed={len(result.failures) + len(result.errors)} skipped={len(result.skipped)}")
raise SystemExit(not result.wasSuccessful())
