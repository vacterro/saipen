"""Run the T-1951 fixtures against the PRE-FIX carrier.

The pair contract needs a measured FAIL, and the FAIL has to be a fact about
the retired-file behaviour rather than about a missing file. This substitutes
the pre-fix `install_ownership.py` into an isolated copy of the fixture and
runs the real `unittest` module against it.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN")
PREFIX = ROOT / ".saipen/evidence/T-1951-install-residue/pre/install_ownership.prefix.py"
FIXTURE = ROOT / "tools/test_t1951_install_residue.py"

spec = importlib.util.spec_from_file_location("t1951_fixture", FIXTURE)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

# Point the fixture's loader at the pre-fix carrier.
def _prefix_ownership():
    spec = importlib.util.spec_from_file_location("t1951_prefix", PREFIX)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

fixture._ownership = _prefix_ownership

suite = unittest.defaultTestLoader.loadTestsFromModule(fixture)
result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
