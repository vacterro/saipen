"""Check the live project after its CLEAN entry against the files saved before it.

Usage: live_clean_verify.py <repo>      (read-only)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
E = repo / ".saipen" / "evidence" / "T-1640-live-clean"
answer = json.loads((E / "transition-clean.json").read_text(encoding="utf-8"))
scrub, seal = answer["board_scrub"], answer["log_seal"]
memory = repo / ".saipen"

board_before = (E / "BOARD.before.md").read_bytes()
log_before = (E / "LOG.before.md").read_bytes()
board_after = (memory / "BOARD.md").read_bytes()
evidence = (repo / scrub["evidence_path"]).read_bytes()
pruned_lines = evidence.splitlines(keepends=True)
before_lines = board_before.splitlines(keepends=True)
drop = set(pruned_lines)
segment = (repo / seal["segment"]).read_bytes()
tail = (memory / "LOG.md").read_bytes().decode("utf-8").splitlines()
added = segment[len(log_before):].decode("utf-8").splitlines()

sys.path.insert(0, str(repo / "tools"))
from saipen_engine.fast_check import validate_project  # noqa: E402
from saipen_engine.log import read_history_snapshot, snapshot_contract_errors  # noqa: E402

snapshot = read_history_snapshot(repo)
checks = {
    "evidence digest is the recorded one": hashlib.sha256(evidence).hexdigest() == scrub["evidence_sha256"],
    "evidence holds one physical BOARD line per pruned record": len(pruned_lines) == scrub["pruned_records"] == len(drop),
    "every evidence line was a BOARD line, in BOARD order": pruned_lines == [l for l in before_lines if l in drop],
    "BOARD after == BOARD before minus exactly those lines": b"".join(l for l in before_lines if l not in drop) == board_after,
    "segment digest is the recorded one": hashlib.sha256(segment).hexdigest() == seal["sealed_sha256"],
    "segment begins with the whole LOG saved before the entry": segment.startswith(log_before),
    "the entry added only its own events before the seal": [
        re.search(r"\[op: ([a-z-]+)-[0-9a-f]+\]", line).group(1) for line in added
    ] == ["transition", "board-scrub"],
    "fresh tail is the heading and the seal's own event": len(tail) == 2 and "DEC: log sealed --" in tail[1],
    "complete ledger passes the immutable-ledger contract": snapshot_contract_errors(snapshot) == [],
    "write gate passes on the result": validate_project(repo) == [],
}
for label, held in checks.items():
    print(f"{'PASS' if held else 'FAIL'}  {label}")
print(f"BOARD {len(board_before)} -> {len(board_after)} bytes; active LOG {len(log_before)} -> "
      f"{(memory / 'LOG.md').stat().st_size} bytes; ledger events {len(snapshot.events)}, tail E-{snapshot.tail}")
print("pruned ids:", ", ".join(scrub["pruned"][:6]), "...", ", ".join(scrub["pruned"][-3:]))
print("RESULT:", "all ten hold" if all(checks.values()) else "NOT PROVEN")
sys.exit(0 if all(checks.values()) else 1)
