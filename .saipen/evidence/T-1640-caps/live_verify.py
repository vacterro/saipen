"""Check the copy after its CLEAN entry against the bytes saved before it."""
import hashlib
import json
import sys
from pathlib import Path

S = Path(sys.argv[1])
copy = S / "live1640"
answer = json.loads((S / "live1640.clean.json").read_text(encoding="utf-8"))
scrub, seal = answer["board_scrub"], answer["log_seal"]

board_before = (S / "live1640.BOARD.before.md").read_bytes()
board_after = (copy / ".saipen" / "BOARD.md").read_bytes()
evidence = (copy / scrub["evidence_path"]).read_bytes()
assert hashlib.sha256(evidence).hexdigest() == scrub["evidence_sha256"]
pruned_lines = evidence.splitlines(keepends=True)
before_lines = board_before.splitlines(keepends=True)
assert len(pruned_lines) == scrub["pruned_records"] == 128, len(pruned_lines)
drop = set(pruned_lines)
assert len(drop) == len(pruned_lines), "a pruned line repeats"
rebuilt = b"".join(line for line in before_lines if line not in drop)
print("BOARD after == BOARD before minus exactly the evidence lines:", rebuilt == board_after)
print("every evidence line was a physical BOARD line:", all(l in before_lines for l in pruned_lines))
print("evidence is in BOARD order:", pruned_lines == [l for l in before_lines if l in drop])
print("bytes:", len(board_before), "->", len(board_after), "evidence", len(evidence))

log_before = (S / "live1640.LOG.before.md").read_bytes()
segment = (copy / seal["segment"]).read_bytes()
assert hashlib.sha256(segment).hexdigest() == seal["sealed_sha256"]
print("segment starts with the LOG saved before the entry:", segment.startswith(log_before))
extra = segment[len(log_before):].decode("utf-8").splitlines()
print("lines the entry itself added before the seal:", len(extra))
for line in extra:
    print("   ", line[:170])
tail = (copy / ".saipen" / "LOG.md").read_bytes().decode("utf-8").splitlines()
print("fresh tail lines:", len(tail))
for line in tail:
    print("   ", line[:330])

sys.path.insert(0, str(copy / "tools"))
from saipen_engine.log import read_history_snapshot, snapshot_contract_errors  # noqa: E402
from saipen_engine.fast_check import validate_project  # noqa: E402

snapshot = read_history_snapshot(copy)
print("ledger contract errors:", snapshot_contract_errors(snapshot), "events", len(snapshot.events), "tail", snapshot.tail)
print("write gate on the result:", validate_project(copy))
