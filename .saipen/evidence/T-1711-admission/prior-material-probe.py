"""Read-only live tree; a disposable control changes the preserved prior input."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "prior-material-probe.json"
if OUTPUT.exists():
    raise SystemExit("Existing evidence is immutable")
sys.path.insert(0, str(ROOT / "tools"))
from test_t1711_regression_execution import ExecutionControls

fixture = ExecutionControls(methodName="test_actual_active_pair_is_admitted_and_typed")
try:
    fixture.setUp()
    admitted = fixture.execute()
    if not admitted.ok:
        raise SystemExit(str(admitted.to_dict()))
    carrier = fixture.project / ".saipen/evidence/before.py"
    original = hashlib.sha256(carrier.read_bytes()).hexdigest()
    carrier.write_text("def answer(): return 99\n", encoding="utf-8")
    changed = hashlib.sha256(carrier.read_bytes()).hexdigest()
    canonical_before = fixture.canonical_digest()
    review = fixture.to_review()
    record = {"probe": "changed prior input after measured execution",
              "admitted": admitted.to_dict(), "prior_sha256": original,
              "changed_prior_sha256": changed, "review": review.to_dict(),
              "canonical_unchanged_after_refusal": canonical_before == fixture.canonical_digest(),
              "scope": "disposable fixture only; no live source or canonical mutation"}
    OUTPUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record))
finally:
    fixture.doCleanups()
