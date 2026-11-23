"""Analyze copied evidence only; compacted receipts remain in the denominator."""
import collections
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
SNAP = OUT / "durable-snapshot"
LIVE = OUT / "live-snapshot"
records = {}
conflicts = []
json_errors = []

def walk(value, path):
    if isinstance(value, dict):
        if all(key in value for key in ("op_id", "operation", "status")):
            identity = value["op_id"]
            if identity in records and records[identity]["record"] != value:
                conflicts.append({"op_id": identity, "paths": [records[identity]["path"], path]})
            else:
                records[identity] = {"path": path, "record": value}
        for child in value.values():
            walk(child, path)
    elif isinstance(value, list):
        for child in value:
            walk(child, path)

for source in (SNAP / ".saipen/recovery").rglob("*.json"):
    try:
        walk(json.loads(source.read_bytes()), source.relative_to(SNAP).as_posix())
    except (ValueError, UnicodeError) as exc:
        json_errors.append({"path": str(source.relative_to(SNAP)), "error": str(exc)})
logs = []
for source in sorted((SNAP / ".saipen/logs").glob("LOG-*.md")):
    logs.append((str(source.relative_to(SNAP)), source.read_text(encoding="utf-8")))
logs.append((".saipen/LOG.md", (LIVE / ".saipen/LOG.md").read_text(encoding="utf-8")))
events = []
for path, body in logs:
    for number, line in enumerate(body.splitlines(), 1):
        match = re.search(r"\[E-(\d+)\]", line)
        if match:
            operation = re.search(r"\[op: ([^\]]+)\]", line)
            events.append({"id": int(match[1]), "path": path, "line": number,
                           "op_id": operation[1] if operation else None, "text": line})
tail = max(e["id"] for e in events)
tagged = [e for e in events if e["op_id"] in records and
          records[e["op_id"]]["record"]["status"] == "COMMITTED"]
ids = {e["id"] for e in events}
latest = sorted(records.values(), key=lambda x: str(x["record"].get("created_at")))[-12:]
record = {"unique_receipts": len(records), "duplicate_record_conflicts": conflicts,
          "json_errors": json_errors,
          "receipt_operations": dict(collections.Counter(x["record"]["operation"] for x in records.values())),
          "log_segments": len(logs), "numbered_events": len(events), "numbered_tail": tail,
          "missing_ids_between_first_and_tail": sorted(set(range(min(ids), tail + 1)) - ids),
          "E3145": [e for e in events if e["id"] == 3145],
          "E3146": [e for e in events if e["id"] == 3146],
          "latest_receipt_backed_event": max(tagged, key=lambda x: x["id"]),
          "latest_receipts": latest,
          "later_core_surface_receipts": [x for x in records.values()
              if str(x["record"].get("created_at", "")) >= "2026-10-08"
              and any(t.get("role") in ("state", "board", "log")
                      for t in x["record"].get("targets", []))]}
(OUT / "durable-analysis.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: record[key] for key in (
    "unique_receipts", "duplicate_record_conflicts", "json_errors", "log_segments", "numbered_events",
    "numbered_tail", "missing_ids_between_first_and_tail", "E3145", "E3146",
    "latest_receipt_backed_event", "later_core_surface_receipts")}, indent=2))
