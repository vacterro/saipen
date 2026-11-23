"""Prepare synthetic disposable gate DATA; never manufacture an operator witness."""
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from test_t1729_operator_gate import ScopedOperatorDecision, capsule

destination = Path(__file__).parent
pointer = destination / "operator-fixture.json"
if pointer.exists():
    raise SystemExit("Existing fixture retained; inspect its pointer instead of replacing it.")
case = ScopedOperatorDecision()
project = case.make()
decision = capsule(
    project,
    expires=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2))
    .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
)
decision["statement"] = (
    "PENDING HUMAN DECISION: replace this draft with the operator's own acceptance "
    "of the synthetic disposable fixture limitation only."
)
draft = destination / "operator-decision-DRAFT.json"
draft.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
pointer.write_text(json.dumps({
    "project_root": str(project), "agent": "tester", "draft": str(draft),
    "gate_id": decision["gate_id"], "expires_at": decision["expires_at"],
    "state": "PREPARED_UNAPPROVED", "fixture_origin": "synthetic test fixture",
    "authority_source_captured": False,
}, indent=2) + "\n", encoding="utf-8")
print(pointer.read_text(encoding="utf-8"))
