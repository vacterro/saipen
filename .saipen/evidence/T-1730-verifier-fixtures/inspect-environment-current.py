"""Compare current verification environment fingerprints without emitting values."""

import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine import regression_execution as execution

record = json.loads((root / ".saipen/recovery/conformance/reverify/RV-000041.json").read_text("utf-8"))["closed_contract"]
_, _, environment = execution._runtime([record["runtime"]["path"], *record["command"][1:]])
keys = {key: hashlib.sha256(value.encode()).hexdigest() for key, value in environment.items()}
old = json.loads((root / ".saipen/evidence/T-1726-closed-contracts/observer-environment-batch.json").read_text("utf-8"))
body = {
    "runtime": sys.executable,
    "expected_digest": record["environment_digest"],
    "current_digest": execution._sha(execution._json(environment)),
    "environment_keys": keys,
    "changed_key_names_from_prior_batch": [key for key in sorted(keys.keys() | old["environment_keys"].keys())
                                           if keys.get(key) != old["environment_keys"].get(key)],
}
target = Path(__file__).with_name("environment-current-" + sys.argv[1] + ".json")
if target.exists():
    raise SystemExit("Existing diagnostic preserved; use a fresh label.")
target.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in body.items() if key != "environment_keys"}, indent=2))
