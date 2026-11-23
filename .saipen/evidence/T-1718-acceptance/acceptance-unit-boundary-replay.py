"""Replay one frozen native regression against exact saved/current module bytes."""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
stage = sys.argv[1]
if stage not in {"before", "after"}:
    raise ValueError("stage must be before or after")
relative = Path("tools/saipen_engine/acceptance_contract.py")
subject = HERE / "repair-before" / relative if stage == "before" else ROOT / relative
name = "saipen_engine.acceptance_contract"
package = importlib.import_module("saipen_engine")
spec = importlib.util.spec_from_file_location(name, subject)
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
package.acceptance_contract = module
oracle = ROOT / "tools/test_t1718_acceptance_contract.py"
print("oracle_sha256", hashlib.sha256(oracle.read_bytes()).hexdigest())
print("subject_sha256", hashlib.sha256(subject.read_bytes()).hexdigest())
suite = unittest.defaultTestLoader.loadTestsFromName(
    "test_t1718_acceptance_contract.NativeEscapeRegressionTests."
    "test_redefined_unit_outcome_cannot_spend_an_old_id_only_pass"
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
