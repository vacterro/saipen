"""Actual native admission counterexamples; never edit the real consumer."""
from __future__ import annotations
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import acceptance
from saipen_engine.log import read_history_snapshot
from saipen_engine.operations import checkpoint, ticket_verify, transition_phase
from test_regression_gate import RegressionGateFixture


class Fixture(RegressionGateFixture):
    REGRESSION = ""


rows = []
for kind in ("delete_required", "optionalize_witness", "fixture_for_live", "ordinary_unchanged"):
    case = Fixture()
    case.setUp()
    base = case.project.parent.resolve()
    assert base.parent == Path(tempfile.gettempdir()).resolve()
    assert base.name.startswith("saipen-regression-gate-")
    try:
        root = case.project
        original = "AC-01 [LIVE] signed-in product outcome"
        if kind == "ordinary_unchanged":
            original = "AC-01 [UNIT] offline inspector outcome"
        result = ticket_verify(root, "T-7", "tester", original)
        assert result.ok, result.to_dict()
        replacement = {
            "delete_required": "offline fixture passes; required product predicate removed",
            "optionalize_witness": "AC-01 [UNIT] signed-in product outcome",
        }.get(kind, original)
        if replacement != original:
            result = ticket_verify(root, "T-7", "tester", replacement)
            assert result.ok, result.to_dict()
        evidence = "AC-EVIDENCE AC-01 PASS behavioral witness=UNIT surface=fixture -- actual fixture-only scope"
        assert checkpoint(root, "tester", "RUN", "T-7", evidence).ok
        assert checkpoint(root, "tester", "RUN", "T-7", "verify -> PASS [target: T-7] conf: high -- fixture gate").ok
        history = read_history_snapshot(root).events
        projection = acceptance.reconcile("T-7", replacement, history)
        admission = transition_phase(root, "REVIEW", "tester", "T-7", "test actual completion admission")
        assert admission.ok, admission.to_dict()
        rows.append({"case": kind, "original": original, "replacement": replacement,
                     "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
                     "replacement_sha256": hashlib.sha256(replacement.encode()).hexdigest(),
                     "projection": projection, "native_review_admission": admission.to_dict(),
                     "unsafe_accepted": kind != "ordinary_unchanged"})
    finally:
        case.doCleanups()
output = HERE / "closure-counterexamples.json"
assert not output.exists()
output.write_text(json.dumps({"scope": "bounded native disposable counterexamples", "cases": rows,
                              "unsafe_admitted": 3, "legitimate_admitted": 1,
                              "production_changed": False}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"unsafe_admitted": 3, "legitimate_admitted": 1,
                  "finding": "acceptance projection does not gate native REVIEW"}))
