"""Independent REVIEW measurements; this writes no lifecycle or kernel receipt."""

import hashlib
import json
from pathlib import Path
import sys

directory = Path(__file__).resolve().parent
root = directory.parents[2]
sys.path.insert(0, str(root / "tools"))
from saipen_engine import core_unit, regression_execution

target = directory / "review-pairs-current-09.json"
if target.exists():
    raise SystemExit("Existing independent review evidence preserved.")
start = core_unit.tree_fingerprint(root)
results = []
try:
    for name in ("regression-contract.json", "diagnostic-regression-contract.json",
                 "cache-regression-matched-current-08.json"):
        path = directory / name
        material = regression_execution._load(root, path)
        row = {"contract": name, "contract_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "verifier": material["verifier"], "runs": []}
        for label, subject in (("before", material["prior"]), ("after", material["current"])):
            outcome = regression_execution._measure(material, label, subject)
            row["runs"].append({key: outcome[key]
                                for key in ("stage", "ran", "failed", "skipped", "exit_code")})
            row["runs"][-1]["output_sha256"] = hashlib.sha256(
                (outcome["stdout"] + outcome["stderr"]).encode()).hexdigest()
        results.append(row)
        print(json.dumps(row), flush=True)
        before, after = row["runs"]
        if not (before["exit_code"] == 1 and before["failed"] > 0
                and after["exit_code"] == 0 and after["failed"] == 0):
            raise RuntimeError("independent comparison disagreed: " + name)
    if core_unit.tree_fingerprint(root) != start:
        raise RuntimeError("public source moved during independent review")
    status = "PASS"
except Exception as error:
    status = "UNVERIFIED"
    results.append({"error": f"{type(error).__name__}: {error}"})
finally:
    target.write_text(json.dumps({"status": status, "fingerprint": start,
                                  "comparisons": results}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "record": str(target)}), flush=True)
raise SystemExit(0 if status == "PASS" else 1)
