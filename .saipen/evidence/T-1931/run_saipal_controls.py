"""Keep the SAIPAL boundary oracle fixed across original and repaired subjects."""

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[3]
ev = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "tools"))
baseline = "--baseline" in sys.argv
subject = ev / "saipal-adapter.before.py" if baseline else root / "tools/saipen_engine/saipal_adapter.py"
if baseline:
    import saipen_engine

    spec = importlib.util.spec_from_file_location("saipen_engine.saipal_adapter", subject)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    saipen_engine.saipal_adapter = module
    spec.loader.exec_module(module)

from test_t1931_saipal_boundary import SaipalBoundaryTests

oracle = root / "tools/test_t1931_saipal_boundary.py"
subject_before = hashlib.sha256(subject.read_bytes()).hexdigest()
oracle_before = hashlib.sha256(oracle.read_bytes()).hexdigest()
suite = unittest.defaultTestLoader.loadTestsFromTestCase(SaipalBoundaryTests)
result = unittest.TextTestRunner(verbosity=1).run(suite)
record = {
    "subject": str(subject.relative_to(root)), "subject_sha256": subject_before,
    "subject_unchanged": subject_before == hashlib.sha256(subject.read_bytes()).hexdigest(),
    "oracle_sha256": oracle_before,
    "oracle_unchanged": oracle_before == hashlib.sha256(oracle.read_bytes()).hexdigest(),
    "tests_run": result.testsRun, "successful": result.wasSuccessful(),
    "failures": [test.id() for test, _ in result.failures],
    "errors": [test.id() for test, _ in result.errors],
    "scope": "local boundary contracts with real isolated CLI processes; no production SAIPAL acceptance",
}
name = "saipal-baseline.json" if baseline else "saipal-current.json"
(ev / name).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, indent=2))
sys.exit(0 if record["subject_unchanged"] and record["oracle_unchanged"]
         and result.wasSuccessful() != baseline else 1)
