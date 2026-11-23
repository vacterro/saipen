"""Two planner implementations, identical frozen tools corpus and required scope.

This measures static planning, not test execution, sandbox-copy performance or
operator verification share. No production .saipen data is excluded from a run:
there is no verification run here, only an explicitly bounded planning corpus.
"""

import importlib.util
import hashlib
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import verification_impact as after

spec = importlib.util.spec_from_file_location("saipen_engine._impact_before",
                                            HERE / "prefix-plan-performance.py")
before = importlib.util.module_from_spec(spec)
spec.loader.exec_module(before)
measurements = []
with tempfile.TemporaryDirectory(prefix="t1836-planning-corpus-") as raw:
    corpus = Path(raw)
    shutil.copytree(ROOT / "tools", corpus / "tools",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".ruff_cache"))
    reference = None
    for name, implementation in (("before", before), ("after", after),
                                  ("after", after), ("before", before)):
        started = time.perf_counter()
        plan = implementation.plan(corpus, ["tools/saipen_engine/efficiency.py"])
        elapsed = time.perf_counter() - started
        scope = {key: plan[key] for key in ("fingerprint", "source_inventory_sha256",
                                           "test_inventory", "selected_tests", "tier")}
        if reference is None:
            reference = scope
        assert scope == reference, "planner optimization changed the required verification scope"
        measurements.append({"implementation": name, "wall_s": elapsed,
                             "inventory": len(plan["test_inventory"]), "tier": plan["tier"]})
    result = {"scope": "frozen tools-only static-planning corpus, no tests executed",
              "scope_identical": True, "source_fingerprint": reference["fingerprint"],
              "source_inventory_sha256": reference["source_inventory_sha256"],
              "runtime": sys.version,
              "before_implementation_sha256": hashlib.sha256(
                  (HERE / "prefix-plan-performance.py").read_bytes()).hexdigest(),
              "after_implementation_sha256": hashlib.sha256(
                  Path(after.__file__).read_bytes()).hexdigest(),
              "measurements": measurements}
    (HERE / "planning-benchmark.json").write_text(json.dumps(result, indent=2) + "\n",
                                                 encoding="utf-8")
    print(json.dumps(result, indent=2))
