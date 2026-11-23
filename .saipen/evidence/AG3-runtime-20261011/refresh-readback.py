"""Refresh the named affected project's metadata without retrying validation."""
import datetime
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "continuation-readback.json"
if OUTPUT.exists():
    raise SystemExit("Existing readback evidence is immutable")
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.paths import prove_owned_dir_chain, prove_owned_regular
from saipen_engine.state import parse_state

affected = Path("V:/___VAC/__K/__CODE/_TAMPERMONKEY/_SUNO_DOWNLOADER")
prove_owned_dir_chain(affected / ".saipen", kind="read-only affected project")
paths = {name: affected / ".saipen" / name for name in
         ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")}
for path in paths.values():
    prove_owned_regular(path, kind="read-only canonical metadata")

def hashes():
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}

before = hashes()
state = parse_state(paths["STATE.md"].read_text(encoding="utf-8-sig"))
after = hashes()
runtime = Path(state["saipen_home"]) / "tools/saipen_engine/audit_manifest.py"
prove_owned_dir_chain(runtime.parent, kind="read-only named runtime")
prove_owned_regular(runtime, kind="read-only named manifest implementation")
runtime_hash = hashlib.sha256(runtime.read_bytes()).hexdigest()
result = {
    "observed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "project_root": str(affected), "observation_identity": "current diagnostic process; not AG3 impersonation",
    "phase": state.get("phase"), "task": state.get("task"), "agent": state.get("agent"),
    "runtime_home": state.get("saipen_home"), "installed_manifest_sha256": runtime_hash,
    "local_fixed_manifest_sha256": hashlib.sha256((ROOT / "tools/saipen_engine/audit_manifest.py").read_bytes()).hexdigest(),
    "before": before, "after": after, "canonical_bytes_unchanged": before == after,
    "validation_retries": 0, "canonical_writes": 0, "acl_mutations": 0,
    "scope": "four canonical files and the exact named runtime module read only; no execution-token or host-access verdict",
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: result[key] for key in ("observed_utc", "phase", "task", "agent",
                  "installed_manifest_sha256", "local_fixed_manifest_sha256", "canonical_bytes_unchanged")}))
if before != after:
    raise SystemExit("Affected canonical metadata changed during readback")
