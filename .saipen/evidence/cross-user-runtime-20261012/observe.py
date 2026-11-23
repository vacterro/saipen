"""Bounded operator-token observations; never claim or repair an AG3 project."""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import codec, lifecycle_authority, log, state
from saipen_engine.board import parse_board

output = HERE / "current-observation.json"
assert not output.exists(), "preserve immutable observation"
roots = [Path("V:/___VAC/__K/__CODE/_PY/_SMART_VAC_CLEANER"),
         Path("V:/___VAC/__K/__CODE/_TAMPERMONKEY/_SUNO_DOWNLOADER")]
names = ["STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md", "MANIFEST.json"]
rows = []
for root in roots:
    before = {name: hashlib.sha256((root / ".saipen" / name).read_bytes()).hexdigest()
              for name in names if (root / ".saipen" / name).is_file()}
    snapshot = state.parse_state(codec.read_doc(root / ".saipen/STATE.md"))
    board = parse_board(codec.read_doc(root / ".saipen/BOARD.md"))
    history = log.read_history_snapshot(root)
    authority = lifecycle_authority.assess(root, snapshot, board, history.events)
    work = {name: ({"section": board["tickets"][name]["section"],
                    "description": board["tickets"][name]["description"],
                    "fields": board["tickets"][name]["fields"]}
                   if name in board["tickets"] else None) for name in ("T-195", "T-199")}
    after = {name: hashlib.sha256((root / ".saipen" / name).read_bytes()).hexdigest() for name in before}
    assert before == after
    rows.append({"project": str(root), "reported_snapshot": {key: snapshot.get(key) for key in
                 ("phase", "task", "next_action", "blocker", "last_event", "agent", "saipen_home")},
                 "board_errors": board["errors"], "history_errors": log.snapshot_contract_errors(history),
                 "current_authority": authority, "work": work, "canonical_hashes": before,
                 "canonical_unchanged": True})

environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                   GIT_OPTIONAL_LOCKS="0", SAIPEN_CAPABILITY="no-publish")
done = subprocess.run([str(HOME / "bin/saipen.cmd"), "--json", "host", "machine", "status"],
                      cwd=HOME, env=environment, capture_output=True, timeout=60)
runtime = json.loads(done.stdout)
value = {"captured_utc": datetime.now(timezone.utc).isoformat(),
         "observer_identity": "current operator token; NOT the AG3 token",
         "consumer_projects": rows, "machine_status": runtime, "machine_status_exit": done.returncode,
         "scope": "read-only declared project records/current protocol interpretation and shared runtime metadata",
         "project_writes": 0, "acl_mutations": 0, "impersonation": False,
         "real_ag3_continuation_verified": False,
         "common_actual_root_cause": "NOT_PROVEN; no current authenticated AG3 operation/token evidence",
         "new_work_created": False, "existing_work": ["T-1647", "T-1652"]}
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"projects": [{"project": row["project"], "authority": row["current_authority"]["status"],
                               "board_errors": row["board_errors"], "history_errors": row["history_errors"],
                               "canonical_unchanged": True} for row in rows],
                  "machine_runtime": runtime.get("code"), "real_ag3_continuation_verified": False}))
