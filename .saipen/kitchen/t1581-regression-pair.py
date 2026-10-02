"""Hold the regression oracle fixed and restore only the pre-fix probe."""

import hashlib
import inspect
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import audit_checks as audit
import test_t1581_phase_rename_knowledge as tests

after = inspect.getsource(audit.phase_rename_probe)
before = after.replace(
    '    knowledge = validate_knowledge(tree)\n'
    '    if knowledge["errors"]:\n'
    '        return "phase rename needs valid knowledge evidence: " + "; ".join(knowledge["errors"])\n',
    "", 1,
).replace(
    "    # Renamed card bodies change the generated projection's source digest.\n"
    "    # Restamp only an index proven fresh before this synthetic mutation;\n"
    "    # existing corrupt evidence must fail rather than be silently repaired.\n"
    '    if knowledge["index"] == "fresh":\n'
    '        indexed = write_index(tree)\n'
    '        if not indexed["ok"]:\n'
    '            return "phase rename could not regenerate the knowledge index: " + indexed["detail"]\n',
    "", 1,
)
if before == after or "knowledge[" in before:
    raise ValueError("The exact implementation delta changed")
namespace = audit.__dict__.copy()
exec(compile(before, str(ROOT / "tools/audit_checks.py"), "exec"), namespace)
results = []
for label, subject in (("FAIL", namespace["phase_rename_probe"]),
                       ("PASS", audit.phase_rename_probe)):
    output = io.StringIO()
    with mock.patch.object(audit, "phase_rename_probe", subject):
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromModule(tests)
        )
    results.append({"expected": label, "passed": result.wasSuccessful(),
                    "ran": result.testsRun, "failures": len(result.failures),
                    "errors": len(result.errors), "output": output.getvalue()})
if results[0]["passed"] or results[0]["failures"] != 1 or not results[1]["passed"]:
    raise ValueError("The same-oracle pre-fix FAIL / post-fix PASS pair did not hold")
evidence = {
    "ticket": "T-1581",
    "verifier_sha256": hashlib.sha256(Path(tests.__file__).read_bytes()).hexdigest(),
    "subject_before_sha256": hashlib.sha256(before.encode("utf-8")).hexdigest(),
    "subject_after_sha256": hashlib.sha256(after.encode("utf-8")).hexdigest(),
    "results": results,
}
target = ROOT / ".saipen/evidence/T-1581-regression-pair-20261001.json"
target.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"pair": "ADMISSIBLE", "tests_per_leg": results[0]["ran"],
                  "record": str(target)}, indent=2))
