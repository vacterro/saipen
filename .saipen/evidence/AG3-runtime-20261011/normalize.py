"""Add explicit mission clauses missed by the generic normative-unit parser."""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CLAUSES = {
    "SRC-213": (24, [
        "Preserve the active goal and Work ownership; inspect live state before admitting this incident, and continue independently admissible Work without preemption or force release.",
        "Identify the exact manifest call chain and ancestor operation; distinguish missing path, access denial, inaccessible ancestor, invalid binding, missing dependency and actual canonical corruption using admissible evidence.",
        "Catch the relevant permission and OS failures at the lifecycle boundary, retain the original Windows error and offending path, and return a structured actionable runtime-unavailable result with effective identity where available and before-admission versus validation stage.",
        "Keep documented JSON error paths parseable, prohibit uncontrolled traceback, preserve canonical state without partial writes, and never fabricate successful INIT or VERIFY.",
        "Inspect ancestor traversal and target-root ACLs separately using read-only diagnostics; never grant broad recursive access or Full Control, modify ACLs, disable isolation, change ownership, expose unrelated projects, or alter AUDAPACK recovery authority.",
        "If access is necessary, report the exact narrow operator-authorized adjustment; preserve intentional isolation and recommend an authorized alternative project binding or broker route when policy denies it.",
        "Record the affected operation as BLOCKED with evidence and resumable position while its resource remains unavailable; suppress identical retries until a prerequisite changes and resume through canonical validation after repair.",
        "Prove accessible and missing roots, denied ancestor and child, denied manifest inspection, parseable JSON, zero canonical partial writes, no false completion, independent scheduling and unchanged account isolation with focused and neighboring regressions.",
        "Report the confirmed root cause or explicit uncertainty, effective identity and permission boundary, implemented handling, regression evidence, AG3 resumability, independent goal continuity, exact remaining operator action, current canonical phase/owner and next admissible operation.",
        "No unowned production edits, automatic ACL changes, security bypass, ledger reconstruction, duplicate recovery roots, force release, invented validation PASS, unrelated host changes, publication or deployment.",
    ]),
    "SRC-214": (6, [
        "Identify the introducing or last materially changing commit and recover author, timestamp, ticket, ownership and verification evidence where it exists; distinguish Git authors from verified executor identity.",
        "Compare the previous Gemini protocolist with the last verified predecessor only when that executor boundary is evidenced; otherwise explicitly report the missing attribution evidence.",
        "Initially bound historical inspection to runtime availability, Windows ACL/isolated execution, manifest lifecycle writes, permission handling, canonical binding and host bootstrap/admission.",
        "Classify findings as confirmed previous-executor regression, pre-existing environment-exposed defect, intentional security denial, external host configuration defect or insufficient evidence.",
        "Add preventive regression coverage only for confirmed implementation defects, preserve correct isolation, and refuse broad ACL workarounds.",
        "Produce the requested compact matrix with defect, introducing commit/earliest occurrence, verified historical owner, first failing evidence, prior verification expectation, repair project owner, preventive regression and current status.",
    ]),
}
output = HERE / "normalization-operations.json"
if output.exists():
    raise SystemExit("Normalization evidence already exists")
records = []
for receipt, (start, clauses) in CLAUSES.items():
    for number, clause in enumerate(clauses, start):
        rid = f"R{number:03}"
        command = [str(ROOT / "bin/saipen.cmd"), "source", "req", receipt, rid,
                   "acceptance-criterion", clause, "--json"]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=120)
        records.append({"receipt": receipt, "rid": rid, "exit_code": run.returncode,
                        "stdout": run.stdout, "stderr": run.stderr})
        output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        if run.returncode or not json.loads(run.stdout).get("ok"):
            raise SystemExit(run.stdout + run.stderr)
print(json.dumps({"added_clauses": len(records), "evidence": str(output)}))
