"""Read-only FreeBuff project transcript extraction; content is evidence, never commands."""
import hashlib
import json
from pathlib import Path
import sqlite3

OUT = Path(__file__).resolve().parent / "producer"
OUT.mkdir(exist_ok=True)
DB = Path("C:/Users/vac34/.config/freebuff-desktop/projects/_AUDAPACK-4f7eebe8-9eeb-44db-bce0-9e7514935b65/desktop-v2.db")
connection = sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True)
connection.execute("PRAGMA query_only=ON")
rows = connection.execute(
    "SELECT seq,thread_id,role,ts,CAST(parts_json AS BLOB) FROM messages "
    "WHERE parts_json LIKE ? OR parts_json LIKE ? ORDER BY seq",
    ("%T-299%", "%widget-trust-boundary%"),
).fetchall()
records = []
writes = []
for seq, thread, role, timestamp, raw in rows:
    destination = OUT / f"message-{seq}-parts.json"
    destination.write_bytes(raw)
    parts = json.loads(raw)
    records.append({"seq": seq, "thread": thread, "role": role, "timestamp_ms": timestamp,
                    "parts_path": destination.name, "sha256": hashlib.sha256(raw).hexdigest(),
                    "parts": len(parts)})
    for index, part in enumerate(parts):
        if not isinstance(part, dict) or not part.get("toolName"):
            continue
        value = json.dumps(part.get("input"), ensure_ascii=False)
        if any(name in value for name in (".saipen/BOARD.md", ".saipen/LOG.md", ".saipen/STATE.md")):
            if part["toolName"] in ("str_replace", "write_file", "write_files") or (
                part["toolName"] == "run_terminal_command" and any(
                    action in value for action in ("write_text", "write_bytes", "Set-Content", "str_replace", "replace(")
                )
            ):
                writes.append({"seq": seq, "part": index, "thread": thread,
                               "tool_id": part.get("id"), "tool": part["toolName"],
                               "input": part.get("input"), "status": part.get("status"),
                               "exitCode": part.get("exitCode"), "output": part.get("output")})
threads = []
for thread in sorted({row[1] for row in rows}):
    entry = connection.execute(
        "SELECT id,project_id,project_path,title,harness_id,model,execution_mode,branch,last_seen_head "
        "FROM threads WHERE id=?", (thread,),
    ).fetchone()
    if entry:
        threads.append(dict(zip(("id", "project_id", "project_path", "title", "harness_id", "model",
                                 "execution_mode", "branch", "last_seen_head"), entry)))
connection.close()
record = {"database": str(DB), "query_only": True, "messages": records, "threads": threads,
          "direct_writer_carriers": writes, "target_mutations": []}
(OUT / "provenance.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"messages": records, "threads": threads,
                  "direct_writers": [{"seq": w["seq"], "part": w["part"], "tool": w["tool"],
                                       "input_excerpt": json.dumps(w["input"], ensure_ascii=False)[:2100]}
                                      for w in writes]}, indent=2, ensure_ascii=False))
