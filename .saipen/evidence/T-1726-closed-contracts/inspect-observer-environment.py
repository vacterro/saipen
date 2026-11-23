"""Local diagnostic; record environment key fingerprints, never values."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import closed_contracts
from saipen_engine import regression_execution as execution

record = json.loads((ROOT / ".saipen/recovery/conformance/reverify/RV-000040.json").read_text(
    encoding="utf-8"))["closed_contract"]
_, _, environment = execution._runtime([record["runtime"]["path"], *record["command"][1:]])
observation = closed_contracts.inspect(ROOT, "T-1695", include_scopes=False)
body = {
    "runtime": sys.executable,
    "expected_digest": record["environment_digest"],
    "current_digest": execution._sha(execution._json(environment)),
    "environment_keys": {key: hashlib.sha256(value.encode()).hexdigest()
                         for key, value in environment.items()},
    "observation": observation,
}
target = Path(__file__).with_name(f"observer-environment-{sys.argv[1]}.json")
target.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"record": str(target), "runtime": body["runtime"],
                  "same_environment": body["expected_digest"] == body["current_digest"],
                  "rows": observation["rows"], "errors": observation["errors"]}, indent=2))
