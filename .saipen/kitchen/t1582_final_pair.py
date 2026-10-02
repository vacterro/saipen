import ast
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools"))
import audit_checks as A
import test_t1582_sweep_skip_reason as oracle

out = root / ".saipen/evidence/T-1582-sweep-candidate"
current = A.mutation_sweep_probe
verifier = (root / "tools/test_t1582_sweep_skip_reason.py").read_bytes()
original = (out / "audit_checks.before.py").read_bytes()
live = (root / "tools/audit_checks.py").read_bytes()
results = []
for variant, subject in (("before", original), ("live", live)):
    node = next(n for n in ast.parse(subject.decode("utf-8")).body
                if isinstance(n, ast.FunctionDef) and n.name == "mutation_sweep_probe")
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(root / "tools/audit_checks.py"),
                 "exec"), A.__dict__)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(oracle)
    )
    (out / f"final-oracle-{variant}.txt").write_text(stream.getvalue(), encoding="utf-8")
    results.append({"variant": variant, "ran": result.testsRun,
                    "failures": len(result.failures), "errors": len(result.errors),
                    "skipped": len(result.skipped), "passed": result.wasSuccessful(),
                    "subject_sha256": hashlib.sha256(subject).hexdigest(),
                    "verifier_sha256": hashlib.sha256(verifier).hexdigest()})
A.mutation_sweep_probe = current
proof = {"oracle_change_reason": "Ruff E501 and py38 floor: format the same mock context without changing setup or assertions",
         "controls": results}
(out / "final-pair.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
print(json.dumps(proof, indent=2))
sys.exit(0 if not results[0]["passed"] and results[1]["passed"] else 1)
