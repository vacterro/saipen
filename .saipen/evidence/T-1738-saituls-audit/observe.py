"""Collect read-only target evidence; write artifacts only in this directory."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
TARGET = Path("V:/___VAC/__K/__CODE/__SAITULS")
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine.board import parse_board  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    preserved = [
        ".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md",
        ".saipen/intake/active/SRC-099.md",
        ".saipen/intake/active/SRC-099.meta.json",
        ".saipen/evidence/T-282-w2-002-ownership-generation.md",
    ]
    before = {name: digest(TARGET / name) for name in preserved}
    board_text = (TARGET / ".saipen/BOARD.md").read_text(encoding="utf-8-sig")
    board = parse_board(board_text)
    state_text = (TARGET / ".saipen/STATE.md").read_text(encoding="utf-8-sig")
    log_text = (TARGET / ".saipen/LOG.md").read_text(encoding="utf-8-sig")
    state = {}
    for key in ("phase", "task", "last_event", "next_action", "continuation_authority"):
        state[key] = re.search(rf"^{key}:\s*(.+)$", state_text, re.M).group(1)
    records = [line for line in board_text.splitlines()
               if re.match(r"^- \[[ x/]\] T-282\s", line)]
    source_meta = json.loads((TARGET / preserved[4]).read_text(encoding="utf-8-sig"))
    receipt_paths = list((TARGET / ".saipen/recovery/conformance").glob(
        "*receipt-66261157f63a_core_FAIL.json"))
    assert len(receipt_paths) == 1, receipt_paths
    receipt_bytes = receipt_paths[0].read_bytes()
    receipt = json.loads(receipt_bytes)
    assert receipt["receipt_id"] == "receipt-66261157f63a"
    assert receipt["verdict"] == "FAIL" and receipt["exit_code"] == 1
    (HERE / "target-core-receipt.json").write_bytes(receipt_bytes)
    (HERE / "target-board.md").write_bytes((TARGET / ".saipen/BOARD.md").read_bytes())
    (HERE / "target-state.md").write_bytes((TARGET / ".saipen/STATE.md").read_bytes())
    good = "## DOING\n## TODO\n- [ ] T-1 [P2] Open work | verify: evidence\n## DONE\n## BLOCKED\n"
    controls = {
        "good": parse_board(good)["errors"],
        "duplicate": parse_board(good.replace("## DONE", "- [ ] T-1 Duplicate\n## DONE"))["errors"],
        "partial": parse_board(good.replace("## TODO", "## PARTIAL"))["errors"],
    }
    assert not controls["good"] and controls["duplicate"] and controls["partial"]
    after = {name: digest(TARGET / name) for name in preserved}
    assert before == after, "Target changed during collection; do not certify this observation"
    observation = {
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "target_root": str(TARGET),
        "target_head": subprocess.check_output(
            ["git", "-C", str(TARGET), "rev-parse", "HEAD"], text=True).strip(),
        "tracked_status_count": len(subprocess.check_output(
            ["git", "-C", str(TARGET), "status", "--porcelain=v1", "-uno"],
            text=True, stderr=subprocess.DEVNULL).splitlines()),
        "state": state, "board_errors": board["errors"],
        "board_headings": board["headings"], "t282_record_count": len(records),
        "t282": board["tickets"].get("T-282"),
        "t282_source_meta_link": source_meta.get("linked_work"),
        "t282_source_body_integrity": before[preserved[3]] == source_meta["source_sha256"],
        "events": [line for line in log_text.splitlines()
                   if re.search(r"\[E-(300[1-9]|301[01])\]", line)],
        "before_sha256": before, "after_sha256": after,
        "collector_preserved_target_inputs": before == after,
        "parser_controls": controls,
        "target_conformance_receipt": {
            "path": str(receipt_paths[0]), "sha256": digest(receipt_paths[0]),
            "verdict": receipt["verdict"],
            "problems": receipt["blocking_findings"]["problem_count"],
            "warnings": receipt["blocking_findings"]["warning_count"],
        },
        "limits": [
            "Canonical validate wrote its conformance receipt; no target Work mutation was requested.",
            "No original duplicate-removal transaction was identified or authorized in this session.",
            "Parser controls prove parser behavior, not target-wide conformance.",
            "MCP excludes tools/ and target memory; conclusions use current direct-source evidence.",
        ],
    }
    (HERE / "observation.json").write_text(json.dumps(observation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"t282_records": len(records), "board_errors": len(board["errors"]),
                      "target_conformance": receipt["verdict"],
                      "problems": receipt["blocking_findings"]["problem_count"],
                      "target_inputs_preserved": before == after}))


if __name__ == "__main__":
    main()
