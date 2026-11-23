"""Read-only scope and model-provenance audit; never manufacture a predecessor."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "attribution-provenance.json"
if OUTPUT.exists():
    raise SystemExit("Existing attribution evidence is immutable")
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.log import read_history_snapshot
from saipen_engine.attempt import build_attempts

snapshot = read_history_snapshot(ROOT, lean=True)
attempts, errors = build_attempts(snapshot.events)
model_records = [value for value in attempts.values()
                 if value.get("runtime_provenance") is not None]
gemini = [value for value in model_records
          if "gemini" in json.dumps(value["runtime_provenance"]).lower()]
event_by_id = {value["event"]: value for value in snapshot.events}
owners = ["audit_manifest.py", "paths.py", "host_bootstrap.py", "machine_runtime.py",
          "protocol_admission.py", "admission.py", "reconcile.py", "init_project.py",
          "isolation_windows.py"]
history = {}
for name in owners:
    relative = "tools/saipen_engine/" + name
    run = subprocess.run(["git", "log", "-8", "--format=%H %aI %an %s", "--", relative],
                         cwd=ROOT, capture_output=True, check=True)
    history[relative] = run.stdout.decode("utf-8", errors="strict")
sealed_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sorted((ROOT / ".saipen/logs").glob("LOG-*.md"))}
controls = []
for event in snapshot.events:
    if (event.get("ticket") in {"T-1494", "T-1693", "T-1701", "T-1706"}
            and any(term in event.get("text", "")
                    for term in ("CORE-UNIT-EVIDENCE", "verify -> PASS", "review -> PASS",
                                 "provider limit", "provider limit", "hot switch"))):
        controls.append(event)
result = {
    "scope": "canonical sealed/active event history and nine requested runtime owners; read-only",
    "history_hash": snapshot.hash, "tail": snapshot.tail,
    "parsed_events": len(snapshot.events), "illegal_history_lines": list(snapshot.illegal_lines),
    "attempt_count": len(attempts), "attempt_errors": errors,
    "model_provenance_count": len(model_records), "gemini_bound_attempts": gemini,
    "runtime_provenance_records": model_records,
    "succession_event": event_by_id.get(14232),
    "nearby_verification_candidates": controls,
    "scoped_git_history": history, "sealed_log_hashes": sealed_hashes,
    "limit": "A host provenance declaration is a declaration, not model authentication. "
             "A nearby green is not the prior executor's verified source predecessor. "
             "No missing model-bound change window or material source snapshot is inferred.",
}
if read_history_snapshot(ROOT, lean=True).hash != snapshot.hash:
    raise SystemExit("History changed during read-only provenance inspection")
for relative, expected in sealed_hashes.items():
    if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
        raise SystemExit("Sealed history changed during inspection")
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"events": result["parsed_events"], "attempts": len(attempts),
                  "attempt_errors": errors, "provenance": len(model_records),
                  "gemini_bound_attempts": len(gemini), "tail": snapshot.tail,
                  "nearby_verification_candidates": len(controls), "evidence": str(OUTPUT)}))
