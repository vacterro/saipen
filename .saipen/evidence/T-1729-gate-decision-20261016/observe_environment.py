"""Record environment hashes for a bounded freshness diagnostic, never values."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.regression_execution import _json, _runtime, _sha

runtime, _, environment = _runtime(["{python}", "-B"])
record = {
    "runtime": runtime,
    "environment_digest": _sha(_json(environment)),
    "keys": {key: hashlib.sha256(value.encode()).hexdigest()
             for key, value in environment.items()},
}
target = Path(__file__).with_name(sys.argv[1])
target.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"record": target.name, "environment_digest": record["environment_digest"]}))
