"""Test the approved candidate in this process, preserving the live product."""
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / "tools"))
import saipen_engine
from saipen_engine import debt

product = root / "tools/saipen_engine/findings.py"
before = product.read_bytes()
candidate_path = here.parent / "T-1765-readonly/candidate-findings.py"
spec = importlib.util.spec_from_file_location("saipen_engine.findings", candidate_path)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
sys.modules["saipen_engine.findings"] = candidate
saipen_engine.findings = candidate
debt.findings_mod = candidate
suite = unittest.defaultTestLoader.discover(str(here), pattern="test_t1765_finding_subtypes.py")
with (here / "candidate-oracle.txt").open("w", encoding="utf-8") as stream:
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
assert product.read_bytes() == before
report = {
    "scope": "isolated candidate; not native product verification",
    "ran": result.testsRun,
    "failed": len(result.failures) + len(result.errors),
    "skipped": len(result.skipped),
    "product_unchanged": True,
    "product_sha256": hashlib.sha256(before).hexdigest(),
    "oracle_sha256": hashlib.sha256((here / "test_t1765_finding_subtypes.py").read_bytes()).hexdigest(),
    "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
}
(here / "candidate-oracle.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(not result.wasSuccessful())
