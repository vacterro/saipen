"""Read-only analysis of the immutable acquisition, never a lifecycle writer."""
from __future__ import annotations

import collections
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent
LOCATION = json.loads((CASE / "location.json").read_text())
ROOT = Path(LOCATION["root"])
SNAP = Path(LOCATION["snapshot"])
HOME = CASE.parents[2]
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import board, codec, journal, lifecycle_authority, log, state


def main():
    memory = SNAP / ".saipen"
    history = log.read_history_snapshot(SNAP)
    parsed_board = board.parse_board(codec.read_doc(memory / "BOARD.md"))
    parsed_state = state.parse_state(codec.read_doc(memory / "STATE.md"))
    pending, conflicts = journal.scan_pending(SNAP)
    # Receipt snapshots are immutable history; a snapshot has a different
    # runtime path, so any unresolved legacy identity refusal is reported.
    receipts = journal.semantic_receipt_snapshot(SNAP)
    records = list(receipts.records)
    by_id = {r.get("op_id"): r for r in records}
    numbered = [e for e in history.events if e.get("event") is not None]
    ordered = sorted(numbered, key=lambda e: int(e["event"]))
    resolved = [e for e in ordered if e.get("op_id") in by_id]
    related = [e for e in ordered if e.get("ticket") in {"T-298", "T-299", "T-300"}]
    related_records = []
    for r in records:
        text = json.dumps(r, ensure_ascii=False)
        if any(re.search(r'(?<![\w-])' + tid + r'(?!\d)', text) for tid in ("T-298", "T-299", "T-300")):
            related_records.append(r)
    (CASE / "related-receipts.json").write_text(json.dumps(related_records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    history_errors = log.snapshot_contract_errors(history)
    report = {
        "root": str(ROOT), "snapshot": str(SNAP), "analysis_subject": "immutable snapshot",
        "state": parsed_state, "board_errors": parsed_board["errors"],
        "headings": parsed_board["headings"], "board_unique_tasks": len(parsed_board["tickets"]),
        "board_task_records": len(re.findall(r'^- \[[ x/]\] T-\d+\b', codec.read_doc(memory / "BOARD.md"), re.M)),
        "history_tail": history.tail, "history_events": len(history.events),
        "history_errors": history_errors, "illegal_history_lines": history.illegal_lines,
        "related_events": related, "recent_events": ordered[-35:],
        "receipts": len(records), "receipt_errors": list(receipts.errors),
        "receipt_statuses": dict(collections.Counter(r.get("status") for r in records)),
        "pending": pending, "conflicts": conflicts,
        "latest_receipted_events": resolved[-12:],
        "latest_receipts": [{k: r.get(k) for k in ("op_id", "operation", "agent", "created_at", "status", "project_identity", "project_lineage", "result")} for r in records[-12:]],
        "authority": lifecycle_authority.assess(SNAP, parsed_state, parsed_board, history.events),
        "related_receipt_count": len(related_records),
    }
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    (CASE / "analysis.json").write_text(encoded, encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("board_unique_tasks", "board_task_records", "board_errors", "headings", "history_tail", "history_events", "history_errors", "illegal_history_lines", "receipts", "receipt_errors", "receipt_statuses", "pending", "conflicts", "latest_receipted_events", "authority", "related_receipt_count")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
