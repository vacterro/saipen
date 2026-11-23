"""Record individually inspected source clauses through the canonical launcher."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "coverage-verified.json"
if OUTPUT.exists():
    raise SystemExit("Existing coverage evidence is immutable")
proof = json.loads((HERE / "verify-green.json").read_text(encoding="utf-8"))
if proof["exit_code"] != 0 or "Ran 21 tests" not in proof["stderr"]:
    raise SystemExit("Focused execution is not proven")
for group in ("verifier_files", "subject_files"):
    for relative, expected in proof[group].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise SystemExit("Focused evidence no longer matches: " + relative)
state = (ROOT / ".saipen/STATE.md").read_text(encoding="utf-8")
if "phase: VERIFY\n" not in state or "task: T-1712\n" not in state:
    raise SystemExit("Current active Work changed")
coverage = json.loads((ROOT / ".saipen/intake/coverage/SRC-213.json").read_text())
if set(coverage["requirements"]) != {f"SRC-213:R{i:03}" for i in range(1, 34)}:
    raise SystemExit("The reviewed source denominator changed")

special = {
    1: "history.json", 2: "read-only-diagnostics.json", 8: "read-only-diagnostics.json",
    9: "owned-application.json", 10: "REPORT.md", 12: "incident.json",
    13: "incident.json", 23: "read-only-diagnostics.json", 24: "REPORT.md",
    25: "preflight.json", 28: "read-only-diagnostics.json", 29: "REPORT.md",
    30: "incident.json", 32: "REPORT.md", 33: "owned-application.json",
}
records = []
for number in range(1, 34):
    rid = f"R{number:03}"
    evidence = ".saipen/evidence/AG3-runtime-20261011/ACCEPTANCE.md"
    verification = ".saipen/evidence/AG3-runtime-20261011/" + special.get(number, "verify-green.json")
    command = [str(ROOT / "bin/saipen.cmd"), "source", "disp", "SRC-213", rid,
               "VERIFIED", "--evidence", evidence, "--verification", verification, "--json"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=120)
    records.append({"rid": rid, "exit_code": run.returncode,
                    "stdout": run.stdout, "stderr": run.stderr})
    OUTPUT.write_text(json.dumps({"scope": "33 individually inspected source clauses; full-family and REVIEW gates remain separate",
                                  "operations": records}, indent=2) + "\n", encoding="utf-8")
    if run.returncode or not json.loads(run.stdout).get("ok"):
        raise SystemExit(run.stdout + run.stderr)
print(json.dumps({"source": "SRC-213", "verified": len(records), "evidence": str(OUTPUT),
                  "full_family_claimed": False, "work_done_claimed": False}))
