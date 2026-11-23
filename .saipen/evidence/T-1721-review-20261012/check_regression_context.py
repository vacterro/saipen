"""Separate byte/context identity from runtime/environment identity, read-only."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import regression_execution as execution

record = json.loads((ROOT / ".saipen/evidence/regression/regression-execution-1bc939dfc7f843148b4a8313c1ebe126.json").read_text())
material = execution._load(ROOT, ROOT / record["contract_path"])
checks = {
    "verifier": material["verifier"] == record["after"]["verifier"],
    "contract_bytes": execution._sha(material["contract_raw"]) == record["contract_sha256"],
    "pre_fix_subject_bytes": execution._sha(execution._json(execution._manifest(material["prior"]))) == record["before"]["subject"],
    "complete_context_bytes": execution._sha(execution._json(execution._manifest(material["context"]))) == record["context_digest"],
    "current_subject_bytes": execution._sha(execution._json(execution._manifest(material["current"]))) == record["after"]["subject"],
    "runtime_path_and_bytes": material["runtime"] == record["runtime"],
}
evidence = {"checks": checks, "runtime": material["runtime"],
            "prior_verifier": record["after"]["verifier"],
            "current_verifier": material["verifier"],
            "environment_values_recorded": False,
            "diagnostic": "Only the environment can differ when contract, full context, both subjects and runtime are equal; its original values were not preserved, so no changed key is attributed."}
output = HERE / "regression-context-diagnostic.json"
if output.exists():
    raise RuntimeError("immutable diagnostic already exists")
output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print(json.dumps(evidence))
