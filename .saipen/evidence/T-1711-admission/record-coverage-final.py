"""Bind completed final-generation clauses; preserve all earlier evidence."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "coverage-final.json"
if OUTPUT.exists():
    raise SystemExit("existing evidence is immutable")
pair = json.loads((HERE / "review-prior-bound-pair.json").read_text(encoding="utf-8"))
native = json.loads((HERE / "native-review-final.json").read_text(encoding="utf-8"))
full_path = ROOT / ".saipen/evidence/core-unit/e2a8fba4c1b7be3c-20261011T095847Z.json"
full = json.loads(full_path.read_text(encoding="utf-8"))
if ([run["exit_code"] for run in pair["runs"]] != [1, 0]
        or native["exit_code"] != 0 or full["verdict"] != "PASS" or full["ran"] != 6198
        or hashlib.sha256(full_path.read_bytes()).hexdigest() !=
        "ebf49162b3bc19870a144a2b09879f01eb9afa084e56d8fc7521654eca7d4087"):
    raise SystemExit("final independent evidence is not complete")
records = []
for number in range(1, 19):
    rid = f"R{number:03}"
    command = [str(ROOT / "bin/saipen.cmd"), "source", "disp", "SRC-212", rid, "VERIFIED",
               "--evidence", ".saipen/evidence/T-1711-admission/ACCEPTANCE-FINAL-GENERATION.md",
               "--verification", ".saipen/evidence/T-1711-admission/REVIEW-FINAL.md", "--json"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=120)
    records.append({"rid": rid, "exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr})
    OUTPUT.write_text(json.dumps({"completed": records}, indent=2) + "\n", encoding="utf-8")
    if run.returncode or not json.loads(run.stdout).get("ok"):
        raise SystemExit(run.stdout + run.stderr)
print(json.dumps({"verified": len(records), "receipt": "SRC-212", "work_done": False}))
