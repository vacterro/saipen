"""One unchanged candidate oracle over either preserved or corrected readers."""

import importlib.util
from pathlib import Path
import sys
import unittest

directory = Path(__file__).resolve().parent
root = directory.parents[2]
sys.path.insert(0, str(root / "tools"))
import saipen_engine
from saipen_engine import closed_contracts, debt, regression_execution

variant = sys.argv[1]
if variant not in {"before", "after"}:
    raise SystemExit("Expected before or after.")
base = directory / ("before-membership-current-08" if variant == "before"
                    else "candidate-membership-current-08")
for name in ("regression_execution", "closed_contracts"):
    spec = importlib.util.spec_from_file_location(
        "saipen_engine." + name, base / "tools/saipen_engine" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    setattr(saipen_engine, name, module)
    spec.loader.exec_module(module)
oracle = directory / "candidate-membership-current-08/tools/test_t1726_closed_contracts.py"
spec = importlib.util.spec_from_file_location("membership_candidate_oracle", oracle)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
names = sys.argv[2:] or [
    "ClosedContracts.test_new_declared_directory_member_invalidates_currentness_before_recheck",
    "ClosedContracts.test_new_explicit_cache_member_is_in_the_declared_dependency_scope",
    "ClosedContracts.test_directory_membership_enumeration_respects_the_shared_path_budget",
]
if names == ["api"]:
    names = ["ClosedContracts." + name
             for name in unittest.defaultTestLoader.getTestCaseNames(module.ClosedContracts)
             if name != "test_native_read_only_cli_paginates_and_never_executes"]
suite = unittest.defaultTestLoader.loadTestsFromNames(names, module)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
