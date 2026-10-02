import hashlib
import importlib
import io
import json
import sys
import types
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools"))
out = root / ".saipen/evidence/T-1586-scenario-candidate"
oracle = importlib.import_module("test_t1586_scenario_inputs")
oracle_bytes = (root / "tools/test_t1586_scenario_inputs.py").read_bytes()
subjects = ["tools/run_scenarios.py", "tools/perf_wave_regressions.py"]
runs = []
for variant in ("before", "live"):
    aggregate = hashlib.sha256()
    details = []
    for symbol, rel in zip(("R", "P"), subjects):
        subject = ((out / (Path(rel).name + ".before")).read_bytes() if variant == "before"
                   else (root / rel).read_bytes())
        aggregate.update(rel.encode("utf-8") + b"\0" + subject + b"\0")
        details.append({"path": rel, "sha256": hashlib.sha256(subject).hexdigest()})
        name = "t1586_final_" + symbol + "_" + variant
        module = types.ModuleType(name)
        module.__file__ = str(root / rel)
        sys.modules[name] = module
        exec(compile(subject.decode("utf-8"), module.__file__, "exec"), module.__dict__)
        module._test_subject_text = subject.decode("utf-8")
        setattr(oracle, symbol, module)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(oracle)
    )
    (out / f"final-oracle-{variant}.txt").write_text(stream.getvalue(), encoding="utf-8")
    runs.append({"variant": variant, "ran": result.testsRun, "failures": len(result.failures),
                 "errors": len(result.errors), "passed": result.wasSuccessful(),
                 "subject_sha256": aggregate.hexdigest(), "subjects": details,
                 "verifier_sha256": hashlib.sha256(oracle_bytes).hexdigest()})
(out / "final-pair.json").write_text(json.dumps(runs, indent=2) + "\n", encoding="utf-8")
print(json.dumps(runs, indent=2))
sys.exit(0 if not runs[0]["passed"] and runs[0]["errors"] == 0 and runs[1]["passed"] else 1)
