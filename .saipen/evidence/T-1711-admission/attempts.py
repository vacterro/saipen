"""Probe cross-attempt evidence using real disposable lifecycle operations."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.operations import attempt_lifecycle
from test_regression_gate import GREEN, S1, S2, V1, RegressionGateFixture, _evidence

output = Path(__file__).with_name("attempts.json")
if output.exists():
    raise SystemExit("Existing reconnaissance evidence is immutable")
fixture = RegressionGateFixture(methodName="runTest")
operations = []
try:
    fixture.setUp()

    def attempt(action, **kwargs):
        answer = attempt_lifecycle(fixture.project, "tester", action, **kwargs)
        payload = answer.to_dict() if hasattr(answer, "to_dict") else answer
        operations.append(payload)
        if not payload.get("ok"):
            raise RuntimeError(payload)

    attempt("open")
    fixture.record(_evidence("FAIL", V1, S1))
    attempt("close", result="failed", stop="validation_failure")
    attempt("open")
    fixture.record(_evidence("PASS", V1, S2))
    attempt("close", result="yielded", stop="deliberate_handoff")
    fixture.record(GREEN)
    before = fixture.canonical_digest()
    answer = fixture.to_review()
    report = {
        "operations": operations,
        "review": answer.to_dict(),
        "zero_writes_on_refusal": fixture.canonical_digest() == before if not answer.ok else None,
        "scope": "FAIL and PASS belong to distinct real attempts on one current VERIFY Work",
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"accepted": answer.ok, "code": answer.code, "evidence": str(output)}))
finally:
    fixture.doCleanups()
