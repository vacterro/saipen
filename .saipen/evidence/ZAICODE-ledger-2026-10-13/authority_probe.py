"""Observe identity, recovery journals and configured launchers without admission."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
TARGET = Path("V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_ZAICODE")
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import journal
from saipen_engine.board import parse_board
from saipen_engine.paths import project_lineage_identity

paths = [TARGET / ".saipen" / n for n in ("STATE.md", "IDENTITY.md", "MANIFEST.json", "BOARD.md")]
before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
pending, conflicts = journal.scan_pending(TARGET)
board = parse_board((TARGET / ".saipen/BOARD.md").read_text(encoding="utf-8-sig"))
registration = Path("C:/ProgramData/SAI/SAIPEN/registration.json")
configured = [HOME / "bin/saipen.cmd", Path("C:/Users/vac34/bin/saipen.cmd"),
              Path("C:/ProgramData/SAI/SAIPEN/bin/saipen.cmd")]
launchers = [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
              "content": p.read_text(encoding="utf-8-sig")} for p in configured]
result = {
    "project_root": str(TARGET.resolve()), "project_lineage": project_lineage_identity(TARGET),
    "target_head": subprocess.check_output(["git", "-C", str(TARGET), "rev-parse", "HEAD"], text=True).strip(),
    "source_home": str(HOME),
    "source_head": subprocess.check_output(["git", "-C", str(HOME), "rev-parse", "HEAD"], text=True).strip(),
    "machine_registration": json.loads(registration.read_text(encoding="utf-8-sig")),
    "launchers": launchers,
    "pending_operations": [{"op_id": p.get("op_id"), "status": p.get("status"), "corrupt": p.get("corrupt")}
                           for p in pending],
    "conflicts": [{"op_id": p.get("op_id"), "status": p.get("status")} for p in conflicts],
    "board_parse_errors": board["errors"],
    "active_claims": [{"ticket": t["id"], "fields": t["fields"]} for t in board["tickets"].values()
                      if t["section"] == "## DOING"],
    "ambient_current_inspector_binding": {key: os.environ.get(key) for key in (
        "SAIPEN_PROJECT_ROOT", "SAIPEN_PROJECT_LINEAGE", "SAIPEN_AGENT")},
    "failing_host_session": "not supplied or identified; current inspector bindings are not historical authority",
    "writer_ownership": "no claim inferred from a lock file; OS writer owner not independently established",
    "recovery_authorization": "none: user handoff grants read-only forensics, not target mutation or continuation",
    "before_sha256": before,
    "after_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
}
assert result["before_sha256"] == result["after_sha256"]
(HERE / "authority.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"lineage": result["project_lineage"], "pending": len(pending),
                  "conflicts": len(conflicts), "active_claims": len(result["active_claims"]),
                  "protected_metadata_stable": True}))
