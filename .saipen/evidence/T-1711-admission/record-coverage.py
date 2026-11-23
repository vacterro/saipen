"""Bind actual completed source clauses; leave the unfinished full gate open."""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "coverage-focused.json"
if OUTPUT.exists():
    raise SystemExit("Existing coverage evidence is immutable")
proof = json.loads((HERE / "verify-final-pair.json").read_text(encoding="utf-8"))
if [run["exit_code"] for run in proof["runs"]] != [1, 0]:
    raise SystemExit("Current paired execution has not passed")
records = []
for number in range(1, 19):
    if number == 17:
        continue
    rid = f"R{number:03}"
    command = [str(ROOT / "bin/saipen.cmd"), "source", "disp", "SRC-212", rid, "VERIFIED",
               "--evidence", ".saipen/evidence/T-1711-admission/ACCEPTANCE.md",
               "--verification", ".saipen/evidence/T-1711-admission/verify-final-pair.json", "--json"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    records.append({"rid": rid, "exit_code": result.returncode,
                    "stdout": result.stdout, "stderr": result.stderr})
    OUTPUT.write_text(json.dumps({"completed": records, "pending": ["R017"]}, indent=2) + "\n",
                      encoding="utf-8")
    if result.returncode or not json.loads(result.stdout).get("ok"):
        raise SystemExit(result.stdout + result.stderr)
print(json.dumps({"verified": len(records), "pending": ["R017"], "work_done": False}))
