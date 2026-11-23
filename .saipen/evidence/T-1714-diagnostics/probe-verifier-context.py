"""Compare transport context by hashes only; never persist environment values."""
import hashlib
import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine import regression_execution as execution

material = execution._load(root, root / ".saipen/evidence/T-1714-diagnostics/regression-contract.json")
record = json.loads((root / ".saipen/evidence/regression/regression-execution-f63225ac11a14d8d914eab879e571504.json").read_bytes())
print(json.dumps({"verifier": material["verifier"], "runtime": material["runtime"],
                  "context_matches": execution._sha(execution._json(execution._manifest(material["context"]))) == record["context_digest"],
                  "before_matches": execution._sha(execution._json(execution._manifest(material["prior"]))) == record["before"]["subject"],
                  "after_matches": execution._sha(execution._json(execution._manifest(material["current"]))) == record["after"]["subject"],
                  "environment": {key: hashlib.sha256(value.encode("utf-8")).hexdigest()
                                  for key, value in material["environment"].items()}}))
