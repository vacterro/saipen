"""Index the full deferred operator specification on its existing queued Work."""
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
source = (HERE / "outcome-first-complete.txt").read_text(encoding="utf-8")
rows = [("requirement", "Fulfill the entire exact SRC-224 mission using existing canonical authority; preserve its user outcome and target state, not just local test counts."),
        ("invariant", "Operator expressly schedules this complete mission after the principal AUDAPACK and cross-user runtime problems; record now, do not implement or preempt those priorities.")]
for number, title in re.findall(r"^PHASE (\d+): (.+)$", source, re.MULTILINE):
    rows.append(("requirement", f"Complete full SRC-224 PHASE {number}: {title}, including every named concept, constraint, decision and deliverable in that original section."))
for letter, title in re.findall(r"^FIXTURE ([A-H]): (.+)$", source, re.MULTILINE):
    rows.append(("acceptance-criterion", f"Execute SRC-224 FIXTURE {letter}: {title}, preserving its exact Expected behavior and meaningful positive/negative controls."))
acceptance = source.split("FINAL ACCEPTANCE\n\n", 1)[1].split("FINAL REPORT", 1)[0]
for number, text in re.findall(r"^(\d+)\. (.+)$", acceptance, re.MULTILINE):
    rows.append(("acceptance-criterion", f"SRC-224 final acceptance {number}: {text}"))
rows.extend([
    ("requirement", "Deliver every item under SRC-224 FINAL REPORT: actual authority/ownership, reused mechanisms, changed locations/contracts, anti-loop and pivot behavior, fixtures, error analysis, full validation/compatibility/recovery, limits and exact next action."),
    ("invariant", "Preserve every SRC-224 NON_GOAL and autonomy constraint: no broad rewrite, consumer code edits from this protocol task, new mandatory server/MCP/controller/authority/queue, speculative pivot, takeover, fabricated history, forced publication, mass reopening or endless analysis."),
])
assert len(rows) == 37
results = []
for number, (kind, text) in enumerate(rows, 1):
    argv = [str(ROOT / "bin/saipen.cmd"), "--json", "source", "req", "SRC-224",
            f"R{number:03d}", kind, text]
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", check=False, timeout=60)
    payload = json.loads(result.stdout)
    results.append({"clause": f"R{number:03d}", "exit_code": result.returncode, "result": payload})
    if result.returncode or not payload.get("ok"):
        raise RuntimeError(json.dumps(results[-1]))
(HERE / "outcome-first-derivation.json").write_text(
    json.dumps({"work": "T-1724", "operator_deferred": True, "results": results},
               indent=2) + "\n", encoding="utf-8")
print(json.dumps({"receipt": "SRC-224", "work": "T-1724", "clauses": len(rows),
                  "phases": 13, "fixtures": 8, "final_acceptance": 12,
                  "implementation_started": False}))
