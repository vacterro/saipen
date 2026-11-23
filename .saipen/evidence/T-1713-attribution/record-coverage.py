"""Adjudicate the original eleven clauses only after actual independent review."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "coverage-final.json"
if OUTPUT.exists():
    raise SystemExit("existing disposition record is immutable")
review = json.loads((HERE / "review-attribution-current.json").read_text(encoding="utf-8"))
controls = json.loads((HERE / "review-instrument-controls.json").read_text(encoding="utf-8"))
full_path = ROOT / ".saipen/evidence/core-unit/55f06a7fce4aa11f-20261011T104946Z.json"
full = json.loads(full_path.read_text(encoding="utf-8"))
if (review.get("ok") is not True or controls.get("ok") is not True
        or [item["accepted"] for item in controls["controls"]] != [True, False, False]
        or full.get("verdict") != "PASS" or full.get("ran") != 6198
        or full.get("fingerprint") != review["tree_fingerprint"]
        or hashlib.sha256(full_path.read_bytes()).hexdigest() !=
        "423a66598cb6e935603085150bc0ff1e165b108222f879f2b123f64165a91c63"):
    raise SystemExit("independent evidence does not satisfy closure")
records = []
for number in range(1, 12):
    rid = f"R{number:03}"
    command = [str(ROOT / "bin/saipen.cmd"), "source", "disp", "SRC-214", rid, "VERIFIED",
               "--evidence", ".saipen/evidence/T-1713-attribution/ACCEPTANCE.md",
               "--verification", ".saipen/evidence/T-1713-attribution/REVIEW.md", "--json"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120)
    stdout = run.stdout.decode("utf-8", errors="replace")
    stderr = run.stderr.decode("utf-8", errors="replace")
    records.append({"rid": rid, "exit_code": run.returncode, "stdout": stdout, "stderr": stderr})
    OUTPUT.write_text(json.dumps({"completed": records}, indent=2) + "\n", encoding="utf-8")
    if run.returncode or not json.loads(stdout).get("ok"):
        raise SystemExit(stdout + stderr)
print(json.dumps({"receipt": "SRC-214", "verified": len(records), "work_done": False}))
