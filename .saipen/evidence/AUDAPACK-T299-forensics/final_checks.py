"""Closing read-only comparison and repeated native integrity checks."""
from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent
HOME = CASE.parents[2]
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import board, codec, journal, lifecycle_authority, log, reconcile, state

location = json.loads((CASE / "location.json").read_text())
ROOT, SNAP = Path(location["root"]), Path(location["snapshot"])
acq = json.loads((SNAP / "ACQUISITION.json").read_text(encoding="utf-8"))
drifts = {"source": [], "snapshot": []}
for record in acq["files"]:
    for kind, root in (("source", ROOT), ("snapshot", SNAP)):
        p = root / record["path"]
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != record["sha256"]:
            drifts[kind].append(record["path"])

history = log.read_history_snapshot(ROOT)
parsed_board = board.parse_board(codec.read_doc(ROOT / ".saipen/BOARD.md"))
parsed_state = state.parse_state(codec.read_doc(ROOT / ".saipen/STATE.md"))
authority = lifecycle_authority.assess(ROOT, parsed_state, parsed_board, history.events)
cut, cut_error = log.foreign_tail_cut(history, codec.read_doc(ROOT / ".saipen/LOG.md"), parsed_state.get("last_event"), authority.get("floor"))
decisions = reconcile.duplicate_id_findings(codec.read_doc(ROOT / ".saipen/BOARD.md"))
pending, conflicts = journal.scan_pending(ROOT)
results = []
for label, argv, cwd in (
    ("native-after", [sys.executable, str(HOME / "tools/validate.py"), "--project-root", str(ROOT), "--gate", "core", "--no-receipt"], ROOT),
    ("recover-preview-after", [str(HOME / "bin/saipen.cmd"), "recover", "--project-root", str(ROOT), "--dry-run", "--json"], ROOT),
    ("git-status-after", ["git", "status", "--porcelain=v1", "--untracked-files=all"], ROOT),
    ("git-head-after", ["git", "rev-parse", "HEAD"], ROOT),
):
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="backslashreplace", timeout=300)
    output = proc.stdout + proc.stderr
    (CASE / (label + ".txt")).write_text(output, encoding="utf-8")
    results.append({"label": label, "argv": argv, "exit_code": proc.returncode, "output_sha256": hashlib.sha256(output.encode()).hexdigest(), "tail": output[-900:]})
report = {"checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "acquired_files_checked": len(acq["files"]), "drifts": drifts,
          "live_authority": authority, "pending": pending, "conflicts": conflicts, "duplicate_findings": decisions,
          "pure_quarantine_predicate": {"cut_proven": cut is not None, "error": cut_error, "live_mutation_attempted": False},
          "commands": results, "audapack_lifecycle_mutations": [], "native_validation": "CURRENT_FAIL"}
(CASE / "final-checks.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"acquired_files_checked": report["acquired_files_checked"], "drifts": drifts, "pending": pending, "conflicts": conflicts,
                  "pure_quarantine_predicate": report["pure_quarantine_predicate"], "duplicate_findings": decisions, "commands": results}, indent=2))
assert not any(drifts.values()), drifts
