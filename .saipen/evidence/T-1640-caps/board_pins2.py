"""Compare three retention rules for a BOARD scrub on a real project."""
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "tools"))
from saipen_engine import intake  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402

text = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
tickets = parse_board(text)["tickets"]
done = {tid for tid, t in tickets.items() if t["section"] == "## DONE"}
live = set(tickets) - done
index = json.loads((root / ".saipen" / "intake" / "index.json").read_text(encoding="utf-8"))
active = set(index.get("active", {}))
receipt_works = set()
for receipt in sorted(active):
    meta = intake._read_meta(root, receipt)
    receipt_works |= intake.linked_works(meta)
    try:
        coverage = intake._read_coverage(root, receipt)
    except (OSError, ValueError):
        coverage = None
    for row in ((coverage or {}).get("requirements") or {}).values():
        work = str((row or {}).get("work") or "").strip()
        if work:
            receipt_works.add(work)
own_receipt = {
    tid
    for tid in done
    if any(
        value.strip() in active
        for value in str(tickets[tid]["fields"].get("source_receipts") or "").split(",")
    )
}
size = lambda ids: sum(len(tickets[i]["raw"].encode("utf-8")) + 1 for i in ids)
token = re.compile(r"\bT-\d+\b")


def machine_refs(t):
    refs = set(t.get("needs", []))
    for key in ("blocked_on", "superseded_by", "implementation_source"):
        refs |= set(token.findall(str(t["fields"].get(key) or "")))
    return refs


def prose_refs(t):
    return set(token.findall(t["raw"])) - {t["id"]}


def closure(seed, edges):
    kept = set(seed)
    frontier = list(seed)
    while frontier:
        tid = frontier.pop()
        for ref in edges(tickets[tid]):
            if ref in tickets and ref not in kept:
                kept.add(ref)
                frontier.append(ref)
    return kept


seed = live | (receipt_works & done) | own_receipt
print("live", len(live), "receipt-named DONE", len(receipt_works & done), "own-receipt DONE", len(own_receipt))
v1 = closure(seed, machine_refs)
live_prose = {ref for tid in live for ref in prose_refs(tickets[tid]) if ref in done}
v2 = closure(seed | live_prose, machine_refs)
v3 = closure(seed, prose_refs)
for name, kept in (("V1 machine", v1), ("V2 +live prose", v2), ("V3 full prose", v3)):
    pruned = done - kept
    print(f"{name:16s} kept DONE {len(kept & done):3d} pruned {len(pruned):3d} "
          f"pruned bytes {size(pruned):6d} board after {len(text.encode('utf-8')) - size(pruned)}")
