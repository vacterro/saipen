"""Read current native receipts and their admission; does not run a verifier."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine import operations, regression_execution  # noqa: E402

folder = Path(__file__).resolve().parent
records = []
for name in ("goal", "diagnosis", "preview", "node", "carrier", "project-launcher-carrier"):
    result = json.loads((folder / f"isolated-{name}-result.json").read_text(encoding="utf-8"))
    record_path = result["record"]
    record = json.loads((root / record_path).read_text(encoding="utf-8"))
    records.append({
        "selection": name,
        "record": record_path,
        "runtime": record["runtime"],
        "verifier": record["verifier"],
        "runs": [{key: run[key] for key in ("stage", "exit_code", "ran", "failed", "skipped")}
                 for run in record["runs"]],
    })
docs, state, _board, _tail = operations._read(root)
full_path = ".saipen/evidence/core-unit/b6dc79950e870846-20261021T220231451753Z.json"
full = json.loads((root / full_path).read_text(encoding="utf-8"))
report = {
    "kind": "read-only receipt observation; no new test execution",
    "phase": state["phase"],
    "task": state["task"],
    "last_event": state["last_event"],
    "latest_executed_gate_problem": regression_execution.evidence_gate(
        root, "T-1844", docs, state,
    ),
    "records": records,
    "full_family": {"record": full_path, **{key: full[key] for key in (
        "verdict", "ran", "red", "problems", "fingerprint", "membership_proof",
    )}},
}
(folder / "isolated-measurements.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8",
)
print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))
