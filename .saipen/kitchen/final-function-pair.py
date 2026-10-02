import ast
import hashlib
import importlib
import io
import json
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools"))
import audit_checks as A
out = (root / sys.argv[1]).resolve()
assert out.is_relative_to(root / ".saipen/evidence")
function_name, test_name = sys.argv[2:4]
oracle = importlib.import_module(test_name)
verifier = (root / "tools" / (test_name + ".py")).read_bytes()
original = (out / "audit_checks.before.py").read_bytes()
live = (root / "tools/audit_checks.py").read_bytes()
saved_function = getattr(A, function_name)
results = []
for variant, subject in (("before", original), ("live", live)):
    node = next(n for n in ast.parse(subject.decode("utf-8")).body
                if isinstance(n, ast.FunctionDef) and n.name == function_name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(root / "tools/audit_checks.py"),
                 "exec"), A.__dict__)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(oracle)
    )
    (out / f"final-oracle-{variant}.txt").write_text(stream.getvalue(), encoding="utf-8")
    results.append({"variant": variant, "ran": result.testsRun,
                    "failures": len(result.failures), "errors": len(result.errors),
                    "passed": result.wasSuccessful(),
                    "subject_sha256": hashlib.sha256(subject).hexdigest(),
                    "verifier_sha256": hashlib.sha256(verifier).hexdigest()})
setattr(A, function_name, saved_function)
proof = {"oracle_change_reason": "Ruff E501 formatting only; repeat both halves with final same verifier",
         "controls": results}
(out / "final-pair.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
print(json.dumps(proof, indent=2))
sys.exit(0 if not results[0]["passed"] and results[0]["errors"] == 0
         and results[1]["passed"] else 1)
