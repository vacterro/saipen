"""Normalize the existing exact audit Source through its canonical owner."""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CLAUSES = [
    "Reproduce the active VERIFY admission incident in disposable protocol fixtures; distinguish reproduced behavior from the reported SAI_WEBSITE history, and preserve any newer live authority before mutation.",
    "Inspect the documented CLI and runtime contract before choosing the repair; never invent verbs merely because a consumer attempted them.",
    "Repair a supported evidence-admission route, or document a compatible operation only where the contract requires one, so genuine regression evidence is admissible while Work is active in VERIFY.",
    "Keep pre-fix failure and post-fix success distinct and bind their correct ticket, attempt, unchanged verifier, source identity and chronological execution.",
    "Make REVIEW evaluate current authoritative evidence; newer failure or authority must supersede stale approval.",
    "Reject forged, unrelated, out-of-order, contradictory and unrecognized-verifier evidence without weakening lifecycle gates.",
    "Preserve historical event chains and previously valid records and lifecycle flows.",
    "Return clear refusal codes and the permitted recovery route when admission is unavailable.",
    "Negative control: missing genuine regression pair refuses admission.",
    "Negative control: failure and success from unrelated attempts refuse admission.",
    "Negative control: stale evidence superseded by newer authority cannot approve REVIEW.",
    "Negative control: unrecognized verifier identity refuses admission.",
    "Positive control: a valid active-ticket pair is admitted through supported operations in a consumer-compatible disposable reproduction.",
    "Replay control: repeated or duplicate evidence creates no duplicated authority.",
    "Compatibility control: tickets without a regression requirement preserve their existing behavior.",
    "Safety: no manual consumer STATE/BOARD/LOG writes, fabricated historical events, weakened review gates, consumer product fixes or unsupported-verb workaround.",
    "Run focused protocol and relevant lifecycle tests, negative controls and the repository-supported complete verification gates; distinguish actual execution from attestation.",
    "Report exact changed runtime files/symbols, root cause and uncertainty, supported CLI/API, red/green identities and totals, compatibility limits and the next permitted operation for the blocked consumer.",
]
output = HERE / "normalization-operations.json"
if output.exists():
    raise SystemExit("Existing normalization evidence is immutable")
records = []
for index, clause in enumerate(CLAUSES, 1):
    rid = f"R{index:03}"
    command = [str(ROOT / "bin/saipen.cmd"), "source", "req", "SRC-212", rid,
               "acceptance-criterion", clause, "--json"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=120)
    records.append({"rid": rid, "exit_code": run.returncode,
                    "stdout": run.stdout, "stderr": run.stderr})
    output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    if run.returncode or not json.loads(run.stdout).get("ok"):
        raise SystemExit(run.stdout + run.stderr)
print(json.dumps({"receipt": "SRC-212", "clauses": len(records), "evidence": str(output)}))
