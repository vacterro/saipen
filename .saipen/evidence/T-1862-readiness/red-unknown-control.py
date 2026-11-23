"""Run the current unknown-input oracle against the staged pre-fix subject."""

import subprocess
import sys
import types
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))

source = subprocess.check_output(
    ["git", "show", ":tools/saipen_engine/readiness.py"], cwd=root
)
pre_fix = types.ModuleType("pre_fix_readiness")
exec(compile(source, "staged:tools/saipen_engine/readiness.py", "exec"), pre_fix.__dict__)

import test_t1862_readiness as oracle  # noqa: E402

oracle.readiness = pre_fix
names = (
    "test_unknown_orphans_block_acceptance",
    "test_failed_audit_classification_blocks_acceptance",
    "test_missing_audit_classification_blocks_acceptance",
    "test_failed_orphan_diagnostic_blocks_acceptance",
    "test_audit_residue_blocks_acceptance",
)
suite = unittest.TestSuite(oracle.UnreadableInputs(name) for name in names)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if result.testsRun != len(names) or len(result.failures) != len(names) or result.errors:
    raise SystemExit("control invalid: expected each pre-fix case to fail its assertion")
print("RED CONTROL HOLDS: five new cases fail on the staged pre-fix subject")
