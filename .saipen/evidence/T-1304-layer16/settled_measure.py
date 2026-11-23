"""Measure the settled-receipt read paths on a disposable copy of the real project.

Usage: settled_measure.py <copy>      (the copy is modified: its legacy index is moved aside)
"""
import sys
import time
from pathlib import Path

copy = Path(sys.argv[1]).resolve()
assert "scratchpad" in copy.as_posix(), copy
sys.path.insert(0, str(copy / "tools"))

from saipen_engine import journal, settled_projection as SP  # noqa: E402
from saipen_engine.paths import project_lineage_identity  # noqa: E402


def timed(label, function, repeat=2):
    best = None
    value = None
    for _ in range(repeat):
        started = time.perf_counter()
        value = function()
        elapsed = time.perf_counter() - started
        best = elapsed if best is None else min(best, elapsed)
    print(f"{label:62s} {best:7.3f} s")
    return value


settled = copy / ".saipen" / "recovery" / "settled"
names = [p.name for p in settled.iterdir() if p.is_dir() and not p.name.startswith(".")]
index_file = settled / ".receipt-index.json"
print("settled receipts:", len(names), "| legacy index bytes:",
      index_file.stat().st_size if index_file.is_file() else None)
lineage = project_lineage_identity(copy)
index = timed("legacy index read (authenticate everything)",
              lambda: journal._read_settled_index(copy, live_lineage=lineage))
print("   legacy index valid:", index is not None)
snap = timed("semantic_receipt_snapshot, legacy index present",
             lambda: journal.semantic_receipt_snapshot(copy))
print("   records", len(snap.records), "errors", len(snap.errors))
timed("semantic_receipt_digest, legacy index present", lambda: journal.semantic_receipt_digest(copy))

head = SP._read_head(copy)
print("bounded projection head present:", head is not None,
      "| deep valid:", SP.validate_projection_deep(copy)[0] if head else None)
rebuilt = timed("settled_projection.rebuild_projection (one deep scan)",
                lambda: SP.rebuild_projection(copy), repeat=1)
print("   ", {k: rebuilt.get(k) for k in ("ok", "code", "sealed_count", "settled_count")})
for operation in ("checkpoint", "seal_log", "no-such-operation"):
    found = timed(f"operation_receipts_bounded({operation!r})",
                  lambda op=operation: SP.operation_receipts_bounded(copy, op))
    print("   records", len(found[0]), "errors", len(found[1]), "projection used", found[2])
token = SP._settled_dir_token(copy)
timed("advance_after_settlement, nothing moved, token current",
      lambda: SP.advance_after_settlement(copy, [], token))

aside = settled.parent / "receipt-index.aside.json"
if index_file.is_file():
    index_file.rename(aside)
snap = timed("semantic_receipt_snapshot, NO legacy index (full scan)",
             lambda: journal.semantic_receipt_snapshot(copy))
print("   records", len(snap.records), "errors", len(snap.errors))
timed("semantic_receipt_digest, NO legacy index (full scan)",
      lambda: journal.semantic_receipt_digest(copy))
if aside.is_file():
    aside.rename(index_file)
