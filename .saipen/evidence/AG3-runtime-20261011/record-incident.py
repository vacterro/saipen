"""Preserve a blocked external validation operation, without claiming its Work."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
output = HERE / "incident.json"
if output.exists():
    raise SystemExit("Incident evidence already exists")
identity = {
    "reported_account": "SAIAG_9fabb0d5",
    "confirmed_account_sid": "S-1-5-21-6247072-3065140091-1424061869-1019",
    "project_root": "V:/___VAC/__K/__CODE/_TAMPERMONKEY/_SUNO_DOWNLOADER",
    "reported_offending_path": "V:/___VAC/__K",
    "reported_windows_error": 5,
    "operation": "post_INIT_manifest_validation",
    "code": "SAIPEN_HOST_RUNTIME_UNAVAILABLE",
}
record = {
    **identity,
    "fingerprint": hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
    "state": "BLOCKED",
    "scope": "external_validation_operation",
    "repair_work": "T-1712",
    "historical_work": "T-1713",
    "canonical_external_readback": {"phase": "PLAN", "task": "none", "agent": "saipen"},
    "external_claim_changed": False,
    "same_token_diagnostics_available": False,
    "resume_position": "Existing bound project: canonical continue and validation after prerequisite repair",
    "required_changed_prerequisites": [
        "Isolation-policy-authorized metadata access or supported authorized binding/broker",
        "Approved runtime carrying the verified repair, accessible to the actual isolated token",
    ],
    "identical_runtime_retry_permitted": False,
    "source_repair_is_deployment": False,
    "main_goal_blocked": False,
    "evidence": ["operator-runtime-request.txt", "read-only-diagnostics.json", "preflight.json",
                 "history.json", "REPORT.md"],
}
output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"state": record["state"], "scope": record["scope"],
                  "fingerprint": record["fingerprint"], "main_goal_blocked": False}))
