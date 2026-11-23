"""Which ACTIVE receipts keep closed BOARD rows, and could they be closed?

Read-only. For every ACTIVE receipt: its Works, whether each is DONE on the
BOARD, and whether its coverage is complete (every clause terminal).
"""
import sys
from collections import Counter
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "tools"))
from saipen_engine import intake  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402

tickets = parse_board((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))["tickets"]
index = intake._read_index(root)
rows = []
for receipt in sorted(index.get("active") or {}):
    meta = intake._read_meta(root, receipt) or {}
    works = sorted(intake.linked_works(meta))
    sections = [tickets[w]["section"][3:] if w in tickets else "ABSENT" for w in works]
    try:
        complete = intake.coverage_complete(root, receipt)
    except (OSError, ValueError) as exc:
        complete = f"unreadable: {exc}"
    try:
        summary = intake.coverage_summary(root, receipt)
        clauses, unresolved = summary["requirements"], len(summary["unresolved"])
    except (OSError, ValueError, KeyError):
        clauses, unresolved = "?", "?"
    rows.append((receipt, works, sections, complete, clauses, unresolved))

shape = Counter()
closable_rows = set()
for receipt, works, sections, complete, clauses, unresolved in rows:
    all_done = bool(works) and all(s == "DONE" for s in sections)
    key = (
        "no linked Work" if not works
        else "complete coverage, every Work DONE" if complete is True and all_done
        else "complete coverage, Work still open" if complete is True
        else "incomplete coverage, every Work DONE" if all_done
        else "incomplete coverage, Work still open"
    )
    shape[key] += 1
    if key == "complete coverage, every Work DONE":
        closable_rows.update(works)
print("ACTIVE receipts:", len(rows))
for key, count in shape.most_common():
    print(f"  {count:4d}  {key}")
size = sum(len(tickets[w]["raw"].encode("utf-8")) + 1 for w in closable_rows if w in tickets)
print("closed BOARD rows held only through receipts whose coverage is complete:",
      len(closable_rows), "rows,", size, "bytes")
sample = [r for r in rows if r[3] is True and r[1] and all(s == "DONE" for s in r[2])][:6]
for receipt, works, sections, complete, clauses, unresolved in sample:
    print("  e.g.", receipt, works, "clauses", clauses, "unresolved", unresolved)
oldest = [r[0] for r in rows if r[3] is True and r[1] and all(s == "DONE" for s in r[2])]
print("first and last such receipt:", oldest[:1], oldest[-1:])
