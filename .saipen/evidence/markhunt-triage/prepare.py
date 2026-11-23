"""Resolve the eight audit records and their immutable filing-pass evidence."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.board import parse_board
from saipen_engine.board_compaction import resolve_detail
from saipen_engine.operations import _read

originals = json.loads((ROOT / ".saipen/evidence/response-authority/blocked-current.json").read_text(encoding="utf-8-sig"))
current = parse_board((ROOT / ".saipen/BOARD.md").read_text(encoding="utf-8"))["tickets"]
history = _read(ROOT)[0]["_history"].events
rows = []
for original in sorted(originals, key=lambda t: t["id"]):
    if original["id"] not in {f"T-{n}" for n in range(1307, 1315)}:
        continue
    fields = dict(original["fields"])
    description = original["description"]
    reference = fields.get("detail_ref")
    chain = []
    seen = set()
    while reference and reference not in seen:
        seen.add(reference)
        detail = resolve_detail(ROOT, reference, expected_ticket_id=original["id"])
        raw = detail["original_record"]
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
        ticket = parse_board("## BLOCKED\n" + text + "\n")["tickets"][original["id"]]
        chain.append({"path": detail["metadata"]["original_record_path"], "sha256": detail["sha256"]})
        if re.search(r"\.\.\.(?:$|\s*\[detail_ref:)", description):
            description = ticket["description"]
        for name, value in ticket["fields"].items():
            if name not in fields or re.search(r"\.\.\.(?:$|\s*\[detail_ref:)", str(fields[name])):
                fields[name] = value
        reference = detail["supersedes_detail_ref"]
    filing = re.search(r"pass (E-\d+)", description)
    pass_id = filing[1] if filing else None
    matching = [e for e in history if str(e.get("event", e.get("id"))) in {pass_id, str(int(pass_id[2:]))}]
    rows.append({"ticket": original["id"], "description": description, "verify": fields.get("verify"),
                 "prior_blocker": fields.get("blocker"), "current_blocker": current[original["id"]]["fields"]["blocker"],
                 "filing_pass": pass_id, "filing_events": matching, "detail_chain": chain})
record = {"kind": "human-triage-preparation-not-approval", "rows": rows,
          "authority": "saipen/phases/markhunt.md:29", "publication_authorized": False}
(DEST / "records.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
for row in rows:
    print(json.dumps({k: row[k] for k in ("ticket", "description", "verify", "filing_pass")}, ensure_ascii=False))
print(json.dumps({"rows": len(rows), "detail_records": sum(len(r["detail_chain"]) for r in rows),
                  "filing_events_found": sum(len(r["filing_events"]) for r in rows)}))
