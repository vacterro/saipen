"""Compare environment value hashes only; never preserve secret values."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import regression_execution as execution  # noqa: E402

mode = sys.argv[1]
runtime, _, environment = execution._runtime(["{python}", "-B"])
result = {
    "runtime": runtime,
    "environment_digest": execution._sha(execution._json(environment)),
    "key_hashes": {key: execution._sha(value.encode("utf-8"))
                   for key, value in environment.items()},
}
path = HERE / ("environment-" + mode + ".json")
path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
previous = HERE / "environment-first.json"
summary = {"mode": mode, "environment_digest": result["environment_digest"]}
if mode != "first" and previous.exists():
    before = json.loads(previous.read_text(encoding="utf-8"))["key_hashes"]
    after = result["key_hashes"]
    summary["different_keys"] = [key for key in sorted(before.keys() | after.keys())
                                 if before.get(key) != after.get(key)]
print(json.dumps(summary))
