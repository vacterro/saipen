"""Replay T-1627 with only the shared test-helper normalization removed.

Run with python -B. Exit 1 means the original tests reproduced their failures;
result JSON separately verifies the exact six historical failure identities.
Production code and repository memory remain unchanged.
"""
from pathlib import Path
import inspect
import json
import sys
import unittest
from unittest.mock import patch

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import test_t1619_iteration_boundary as owner
import test_t1627_operator_question as target

normalization = (
    '    if fields.get("execution_intent") == "goal":\n'
    '        text = re.sub(r"(?m)^converge_target:.*\\n", "", text)\n'
)
source = inspect.getsource(owner._seat)
assert source.count(normalization) == 1, "Expected shared fixture repair absent or changed"
assert "converge_target: crew" in owner.REAL_STATE, "Replay requires the observed converge/crew seed"
namespace = dict(vars(owner))
exec(compile(source.replace(normalization, "", 1), "<old shared test helper>", "exec"), namespace)
expected = set(json.loads((EVIDENCE / "historical-red-sections.json").read_text(encoding="utf-8")))

with patch.object(owner, "_seat", namespace["_seat"]), patch.object(target, "_seat", namespace["_seat"]):
    suite = unittest.defaultTestLoader.loadTestsFromModule(target)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

failures = sorted(test.id() for test, _ in result.failures)
summary = {
    "method": "Remove only the two-line test-helper normalization in memory; run all original operator tests",
    "tests_run": result.testsRun,
    "failures": failures,
    "errors": [test.id() for test, _ in result.errors],
    "skipped": [test.id() for test, _ in result.skipped],
    "matches_historical_six": set(failures) == expected,
}
(EVIDENCE / "old-helper-result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
assert result.testsRun == 16, summary
assert set(failures) == expected, summary
assert not result.errors and not result.skipped, summary
print("CONTROLLED REPRODUCTION: exact historical six failures; zero errors/skips", flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
