"""Read-only contract/material check; this never executes or attests the pair."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.regression_execution import _load

material = _load(root, Path(__file__).with_name("regression.json"))
result = {
    "status": "MATERIAL_VALIDATED_ONLY",
    "pair_executed": False,
    "contract_path": material["contract_path"],
    "context_files": len(material["context"]),
    "context_bytes": sum(len(body or b"") for body in material["context"].values()),
    "subject_files": list(material["current"]),
    "oracle_files": material["contract"]["oracle_files"],
    "verifier": material["verifier"],
    "argv": material["argv"],
    "next": "After T-1793 finishes, resume T-1792 and enter VERIFY; only native work regression executes and records the pair.",
}
Path(__file__).with_name("pair-input-check.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result))
