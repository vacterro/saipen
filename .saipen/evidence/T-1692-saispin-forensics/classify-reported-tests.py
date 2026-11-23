"""Attribute supplied observations without manufacturing process evidence."""
import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
source = root / ".saipen/intake/active/SRC-198.md"
body = source.read_bytes()
observations = [
    ("python tests/test_saispin.py", "PASS after weakened predicate", "PASS", None, None),
    ("python -m pytest tests/test_saispin.py", "0 items collected", "TEST_DISCOVERY_EMPTY", 0, None),
    ("Scripts/saispin_watch.ps1 -SelfTest", "PASS in one run", "PASS", None, None),
    ("tests/test_saispin_settings.ps1", "PASS in one run", "PASS", None, None),
    ("tests/test_saispin_task.ps1", "nine failures in a separate run", "TEST_FAILURE", None, 9),
    ("other tests/test_saispin_task.ps1 invocations (exact arguments unavailable)",
     "Register-ScheduledTask : Access is denied", "PERMISSION_DENIED", None, None),
]
rows = []
for number, (command, result, category, collected, failed) in enumerate(observations, 1):
    rows.append({
        "command": command,
        "execution_environment": "reported Windows SAITULS session; exact token/environment unavailable",
        "exit_code": None,
        "tests_collected": collected,
        "tests_passed": None,
        "tests_failed": failed,
        "tests_skipped": None,
        "tests_blocked": None,
        "fixture_isolation": "historical fixture state unverified; production lease writes reported",
        "baseline_revision": None,
        "changed_source_revision": None,
        "evidence_identity": {
            "receipt": "SRC-198",
            "source_sha256": hashlib.sha256(body).hexdigest(),
            "observation": f"F-05:{number:03d}",
            "raw_stream_available": False,
        },
        "reported_result": result,
        "classification": category,
        "blocked_acceptance": category == "PERMISSION_DENIED",
        "attribution": "operator-supplied incident account; not independently executed",
        "current_acceptance": False,
    })
report = {
    "schema_version": 1,
    "scope": "intake attribution only; null means unavailable, never zero or PASS",
    "aggregate_pass": False,
    "product_tests_executed_by_intake": 0,
    "observations": rows,
}
target = here / "reported-tests.json"
target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"report": str(target), "observations": len(rows), "aggregate_pass": False}))
