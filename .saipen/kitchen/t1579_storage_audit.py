"""Read-only bounded inventory; no migration or runtime execution."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import autoinject
from saipen_engine import codec
from saipen_engine.state import parse_state
from saipen_engine.storage import classify_path, effective_ephemeral_roots, load_policy
from saipen_engine.storage_artifacts import validate_storage

policy = load_policy()
projects = []
violations = []
errors = []
for project in sorted(ROOT.parent.iterdir()):
    memory = project / ".saipen"
    if not project.is_dir() or not (memory / "STATE.md").is_file():
        continue
    try:
        state = parse_state(codec.read_doc(memory / "STATE.md"))
        row = {"project": str(project), "state_path": str(memory), "paths": []}
        for purpose, path in (("project canonical state", memory),
                              ("bound runtime home", state.get("saipen_home"))):
            if not path:
                continue
            verdict = classify_path(path, "DURABLE", policy=policy, base=project)
            row["paths"].append({"purpose": purpose, **verdict})
            if verdict["code"] == "STORAGE_POLICY_VIOLATION":
                violations.append({"project": str(project), "purpose": purpose, **verdict})
        declared = any((memory / name).exists() for name in
                       ("STORES.json", "STORAGE_REGISTRY.json"))
        row["storage_declared"] = declared
        if declared:
            row["storage_findings"] = validate_storage(project, policy=policy)
            violations.extend({"project": str(project), **finding}
                              for finding in row["storage_findings"])
        projects.append(row)
    except (OSError, ValueError) as error:
        errors.append({"project": str(project), "error": str(error)})

runtimes = []
for home in autoinject.registry_targets():
    verdict = classify_path(home, "DURABLE", policy=policy)
    row = {"home": str(home), "exists": home.is_dir(), **verdict}
    runtimes.append(row)
    if row["exists"] and verdict["code"] == "STORAGE_POLICY_VIOLATION":
        violations.append({"purpose": "installed runtime home", **row})

home = Path("V:/___VAC/__K/__STATE/SAILEARN_HOME")
marker = home / "RECOVERY_PENDING.md"
report = {
    "recorded_at": datetime.now(timezone.utc).isoformat(),
    "scope": "Immediate project siblings with .saipen/STATE.md plus adapter-registry runtime homes; no recursive disk discovery.",
    "limitations": "An unknown root has no durable trust. This inventory does not inspect arbitrary third-party model registries, remote hosts or undeclared projects.",
    "effective_ephemeral_roots": [str(root) for root in effective_ephemeral_roots(policy)],
    "projects": projects, "runtime_homes": runtimes,
    "violations": violations, "read_errors": errors,
    "sailearn": {
        "home": str(home), "verdict": classify_path(home, "DURABLE", policy=policy),
        "source_repository_available": any("sailearn" in row["project"].lower() for row in projects),
        "recovery_marker": str(marker),
        "marker_sha256": hashlib.sha256(marker.read_bytes()).hexdigest() if marker.is_file() else None,
        "migration_actions_this_turn": [], "model_history_rebuilt": False,
    },
}
target = ROOT / ".saipen/evidence/T-1579-storage-safety/storage-audit.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"report": str(target), "projects": len(projects),
                  "runtime_homes": len(runtimes), "violations": violations, "read_errors": errors}))
