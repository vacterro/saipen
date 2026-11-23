"""Read-only reconnaissance of current admission, using disposable fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from test_regression_gate import GREEN, S1, S2, V1, RegressionGateFixture, _evidence


def case(name, records, *, regression="required"):
    fixture = RegressionGateFixture(methodName="runTest")
    fixture.REGRESSION = regression
    try:
        fixture.setUp()
        for record in records:
            fixture.record(record)
        fixture.record(GREEN)
        before = fixture.canonical_digest()
        answer = fixture.to_review()
        return {
            "case": name,
            "result": answer.to_dict(),
            "refusal_preserves_canonical_bytes": (
                fixture.canonical_digest() == before if not answer.ok else None
            ),
        }
    finally:
        fixture.doCleanups()


results = [
    case("missing_pair", []),
    case("documented_active_pair", [
        _evidence("FAIL", V1, S1), _evidence("PASS", V1, S2),
    ]),
    case("unregistered_digest_without_executed_verifier", [
        _evidence("FAIL", "1234abcd", S1),
        _evidence("PASS", "1234abcd", S2),
    ]),
    case("contradictory_duplicate_identity", [
        _evidence("FAIL", V1, S1) + " verifier:9999dddd",
        _evidence("PASS", V1, S2),
    ]),
    case("newer_failure_invalidates_approval", [
        _evidence("FAIL", V1, S1), _evidence("PASS", V1, S2),
        _evidence("FAIL", V1, S1),
    ]),
    case("ordinary_undeclared_ticket", [], regression=""),
]
output = Path(__file__).with_name("preflight.json")
if output.exists():
    raise SystemExit("Existing reconnaissance evidence is immutable")
output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"cases": [{"case": r["case"], "accepted": r["result"]["ok"]}
                            for r in results], "evidence": str(output)}))
