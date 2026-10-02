"""Run the T-1557 telegram regression against original or isolated candidate code."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools"))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mode = sys.argv[1]
if mode == "candidate":
    import saipen_engine

    saipen_engine.telegrams = load(
        "saipen_engine.telegrams",
        SCRATCH / "candidate/tools/saipen_engine/telegrams.py",
    )
    load("saipen", SCRATCH / "candidate/tools/saipen.py")
elif mode != "original":
    raise SystemExit("usage: run_candidate.py original|candidate")

tests = load("test_t1497_candidate", SCRATCH / "candidate/tools/test_t1497_turn_entry_telegrams.py")
suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
