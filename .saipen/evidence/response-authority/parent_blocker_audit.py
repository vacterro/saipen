"""Read and bind the bounded T-1510 blocker audit; no canonical writes."""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.board import parse_board
from saipen_engine.board_compaction import resolve_detail
from saipen_engine.operations import _read
from saipen_engine.retirement import non_work_event

DEST = Path(__file__).resolve().parent
board_bytes = (ROOT / ".saipen/BOARD.md").read_bytes()
board = parse_board(board_bytes.decode("utf-8-sig"))
rows = []
for ticket in board["tickets"].values():
    if ticket["section"] != "## BLOCKED":
        continue
    ref = ticket["fields"].get("detail_ref")
    details = []
    fields = dict(ticket["fields"])
    seen = set()
    while ref and ref not in seen:
        seen.add(ref)
        resolved = resolve_detail(ROOT, ref, expected_ticket_id=ticket["id"])
        raw = resolved["original_record"]
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
        original = parse_board("## BLOCKED\n" + text + "\n")["tickets"][ticket["id"]]
        details.append({"path": resolved["metadata"]["original_record_path"], "sha256": resolved["sha256"]})
        for name, value in original["fields"].items():
            current = str(fields.get(name, ""))
            truncated = bool(re.search(r"\.\.\.(?:$|\s*\[detail_ref:)", current))
            if truncated or name not in fields:
                fields[name] = value
        ref = resolved["supersedes_detail_ref"]
    rows.append({"ticket": ticket["id"], "fields": fields, "details": details,
                 "dependencies": {d: board["tickets"][d]["section"] for d in ticket["needs"]}})

result = {"board_sha256": hashlib.sha256(board_bytes).hexdigest(), "blocked": len(rows), "rows": rows}
history = _read(ROOT)[0]["_history"].events
result["non_work_history"] = {
    r["ticket"]: event["event"] if "event" in event else event.get("id")
    for r in rows if (event := non_work_event(r["ticket"], history)) is not None
}
result["canonical_hashes"] = {
    p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
    for p in (".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md")
}
label = sys.argv[1] if len(sys.argv) > 1 else "expanded"
assert re.fullmatch(r"[a-z0-9-]+", label)
(DEST / f"parent-blockers-{label}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
print(json.dumps({"ok": True, "blocked": len(rows), "detail_records": sum(len(r["details"]) for r in rows)}))
