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
out = root / ".saipen/evidence/T-1585-amnesty-candidate"
oracle = importlib.import_module("test_t1585_amnesty_control")
verifier = (root / "tools/test_t1585_amnesty_control.py").read_bytes()
runs = []
for variant, subject in (("before", (out / "audit_checks.before.py").read_bytes()),
                         ("live", (root / "tools/audit_checks.py").read_bytes())):
    name = "t1585_final_" + variant
    module = types.ModuleType(name)
    module.__file__ = str(root / "tools/audit_checks.py")
    sys.modules[name] = module
    exec(compile(subject.decode("utf-8"), module.__file__, "exec"), module.__dict__)
    oracle.A = module
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(oracle)
    )
    (out / f"final-oracle-{variant}.txt").write_text(stream.getvalue(), encoding="utf-8")
    runs.append({"variant": variant, "ran": result.testsRun, "failures": len(result.failures),
                 "errors": len(result.errors), "passed": result.wasSuccessful(),
                 "subject_sha256": hashlib.sha256(subject).hexdigest(),
                 "verifier_sha256": hashlib.sha256(verifier).hexdigest()})
(out / "final-pair.json").write_text(json.dumps(runs, indent=2) + "\n", encoding="utf-8")
print(json.dumps(runs, indent=2))
sys.exit(0 if not runs[0]["passed"] and runs[0]["errors"] == 0 and runs[1]["passed"] else 1)
