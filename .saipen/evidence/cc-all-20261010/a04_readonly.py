"""Recheck the roadmap's existing AUDAPACK forensic matrix without mutation."""

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
HOME_ROOT = OUT.parents[2]
TARGET = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK")
sys.path.insert(0, str(HOME_ROOT / "tools"))
from saipen_engine import board, codec, journal, lifecycle_authority, log, state

destination = OUT / "A04-current.json"
if destination.exists():
    raise SystemExit("existing evidence is immutable")

names = ("STATE.md", "BOARD.md", "LOG.md", "MANIFEST.json")
before = {name: hashlib.sha256((TARGET / ".saipen" / name).read_bytes()).hexdigest() for name in names}
baseline = json.loads((HOME_ROOT / ".saipen/evidence/T-1704-draft/AUDAPACK-final-integrity.json").read_text(encoding="utf-8"))
history = log.read_history_snapshot(TARGET)
board_text = codec.read_doc(TARGET / ".saipen/BOARD.md")
parsed_board = board.parse_board(board_text)
parsed_state = state.parse_state(codec.read_doc(TARGET / ".saipen/STATE.md"))
authority = lifecycle_authority.assess(TARGET, parsed_state, parsed_board, history.events)
pending, conflicts = journal.scan_pending(TARGET)
events = {event.get("event"): event for event in history.events}
gaps = [{"child": child, "parent": events.get(child, {}).get("parent"), "parent_present": parent in events}
        for child, parent in ((3134, 3133), (3137, 3136), (3146, 3145))]
commands = []
for label, argv in (
    ("A04-status", [str(HOME_ROOT / "bin/saipen.cmd"), "status", "--project-root", str(TARGET), "--json"]),
    ("A04-recover", [str(HOME_ROOT / "bin/saipen.cmd"), "recover", "--project-root", str(TARGET), "--dry-run", "--json"]),
    ("A04-next", [str(HOME_ROOT / "bin/saipen.cmd"), "next", "--project-root", str(TARGET), "--json"]),
    ("A04-native", [sys.executable, "-B", str(HOME_ROOT / "tools/validate.py"), "--project-root", str(TARGET), "--gate", "core", "--no-receipt"]),
):
    result = subprocess.run(argv, cwd=TARGET, stdin=subprocess.DEVNULL, capture_output=True, timeout=300, check=False)
    raw = result.stdout + result.stderr
    output = OUT / (label + ".txt")
    output.write_bytes(raw)
    try:
        payload = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        payload = None
    commands.append({"argv": argv, "exit_code": result.returncode, "output": str(output.relative_to(HOME_ROOT)).replace("\\", "/"),
                     "output_sha256": hashlib.sha256(raw).hexdigest(), "payload": payload,
                     "native_summary": re.findall(r"Validation (?:FAILED|complete)[^\r\n]*", raw.decode("utf-8", errors="replace"))})

after = {name: hashlib.sha256((TARGET / ".saipen" / name).read_bytes()).hexdigest() for name in names}
report = {
    "checked_utc": datetime.now(timezone.utc).isoformat(),
    "target": str(TARGET), "before": before, "after": after,
    "core_unchanged": before == after,
    "matches_original_core": all(before[name] == baseline["original_core"][name]["expected"] for name in names),
    "state": parsed_state, "board_errors": parsed_board["errors"],
    "history_errors": log.snapshot_contract_errors(history),
    "history_illegal_lines": history.illegal_lines, "history_tail": history.tail,
    "missing_parent_matrix": gaps, "lifecycle_authority": authority,
    "pending": pending, "conflicts": conflicts, "commands": commands,
    "live_mutations": 0,
    "classification": "READ_ONLY_DIAGNOSIS_ONLY; original lifecycle corruption remains unresolved",
    "limits": "Only the four original core bytes and current owner projections were rechecked. No claim that every acquired case file or an unavailable external backup was searched.",
}
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
assert before == after, "consumer core changed during observation; do not claim stable evidence"
print(json.dumps({"core_unchanged": report["core_unchanged"], "matches_original_core": report["matches_original_core"],
                  "floor": authority.get("floor"), "authority": authority.get("status"),
                  "unbacked_terminal_tickets": [finding.get("ticket") for finding in authority.get("findings", []) if finding.get("ticket")],
                  "commands": [{"command": row["argv"][1:4], "exit_code": row["exit_code"], "code": (row["payload"] or {}).get("code"), "native_summary": row["native_summary"]} for row in commands]}))
