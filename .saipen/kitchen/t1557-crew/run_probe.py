"""Run baseline or candidate in memory; write only this scratch directory."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import subs  # noqa: E402

mode = sys.argv[1]
if mode == "candidate":
    source = (HERE / "subs.py.candidate").read_text(encoding="utf-8")
    exec(compile(source, subs.__file__, "exec"), subs.__dict__)
elif mode != "baseline":
    raise ValueError(mode)

import test_crew_applicability  # noqa: E402

test_module = types.ModuleType("test_sub_style_contract")
test_module.__file__ = str(ROOT / "tools" / "test_sub_style_contract.py")
sys.modules[test_module.__name__] = test_module
exec(
    compile(
        (HERE / "test_sub_style_contract.py").read_text(encoding="utf-8"),
        test_module.__file__,
        "exec",
    ),
    test_module.__dict__,
)
suite = unittest.TestSuite(
    [
        unittest.defaultTestLoader.loadTestsFromModule(test_module),
        unittest.defaultTestLoader.loadTestsFromTestCase(test_crew_applicability.RosterStageTests),
    ]
)
with (HERE / f"{mode}.log").open("w", encoding="utf-8") as log:
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
print(f"{mode}: tests={result.testsRun} failures={len(result.failures)} errors={len(result.errors)}")
print((HERE / f"{mode}.log").read_text(encoding="utf-8"))
sys.exit(not result.wasSuccessful())
