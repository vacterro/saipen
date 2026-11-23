"""Verify current subject/oracle bytes against the committed measured pair."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.journal import hash_bytes, semantic_receipts_for_operation_safe  # noqa: E402

records, errors = semantic_receipts_for_operation_safe(ROOT, "regression_execution")
if errors:
    raise RuntimeError(errors)
record = next(item for item in records if item["op_id"] ==
              "regression-execution-3d494d7f7c0b4320919fe69bdd194448")
paths = [
    "tools/saipen.py", "tools/saipen_engine/operations.py",
    "tools/saipen_engine/reconcile.py", "tools/saipen_engine/gate_decision.py",
    "tools/saipen_engine/state.py", "tools/saipen_engine/router.py",
    "tools/saipen_engine/operator_task.py", "tools/saipen_engine/goal_authority.py",
    "tools/test_t1729_operator_gate.py", "tools/test_recovery_reachability.py",
    "tools/test_fixture_support.py", "tools/test_hermetic_env.py",
]
dependencies = record["read_preconditions"]
changed = [path for path in paths if hash_bytes((ROOT / path).read_bytes()) !=
           dependencies.get(path)]
print(json.dumps({"op_id": record["op_id"], "checked": paths, "changed": changed,
                  "bounded_code_and_oracle_unchanged": not changed}, indent=2))
raise SystemExit(bool(changed))
