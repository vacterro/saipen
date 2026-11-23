"""Extract bounded writer evidence and preserve both engineering subjects."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import stat
from pathlib import Path

CASE = Path(__file__).resolve().parent
ROOT = Path(json.loads((CASE / "location.json").read_text())["root"])
CAPTURE = CASE / "provenance-capture"
db = CAPTURE / "freebuff-desktop-v2.db"
conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM messages WHERE parts_json LIKE ?", ("%T-299%",)).fetchall()
report = {"database_sha256": hashlib.sha256(db.read_bytes()).hexdigest(), "writers": [], "engineering": []}
for row in rows:
    thread = dict(conn.execute("SELECT id,project_path,title,harness_id,model,agent_mode,status,turn_state,created_at,updated_at FROM threads WHERE id=?", (row["thread_id"],)).fetchone())
    target = CAPTURE / ("freebuff-message-" + str(row["seq"]) + ".json")
    raw = (json.dumps(dict(row), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if not target.exists():
        target.write_bytes(raw)
        target.chmod(stat.S_IREAD)
    assert target.read_bytes() == raw
    parts = json.loads(row["parts_json"])
    direct_writes = []
    engineering_runs = []
    for part in parts:
        inp = part.get("input") or {}
        if part.get("kind") != "tool":
            continue
        if inp.get("path") in {".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md"} or (
            part.get("toolName") == "run_terminal_command" and ".saipen/LOG.md" in inp.get("command", "")
        ):
            direct_writes.append(part)
        if part.get("toolName") == "run_terminal_command" and any(s in inp.get("command", "") for s in ("pytest", "ruff", "compileall")):
            engineering_runs.append(part)
    report["writers"].append({"thread": thread, "message_seq": row["seq"], "message_ts_ms": row["ts"],
                              "role": row["role"], "message_sha256": hashlib.sha256(raw).hexdigest(),
                              "direct_writes": direct_writes, "engineering_runs": engineering_runs})
conn.close()

for rel in ("audapack/saipen_evidence.py", "tests/test_saipen_evidence.py", "resources/AUDAPACK_WIDGET.user.js", "resources/AUDAPACK_WIDGET.release.json", "tests/widget/w7-016-send-age-and-archive-timestamp.test.js", "tests/widget/harness.js", "docs/AUDAPACK_WIDGET_ACCEPTANCE.md", "_widget_sweep.out"):
    source = ROOT / rel
    if not source.is_file():
        report["engineering"].append({"path": rel, "present": False})
        continue
    raw = source.read_bytes()
    target = CAPTURE / "engineering" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(raw)
        target.chmod(stat.S_IREAD)
    assert target.read_bytes() == raw
    assert source.read_bytes() == raw
    report["engineering"].append({"path": rel, "present": True, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "source_mtime_ns": source.stat().st_mtime_ns})
(CASE / "writer-and-engineering.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"writers": [{"thread": w["thread"], "message_seq": w["message_seq"], "message_ts_ms": w["message_ts_ms"], "direct_writes": [{"toolName": p.get("toolName"), "id": p.get("id"), "path": p.get("input", {}).get("path"), "status": p.get("status"), "exitCode": p.get("exitCode")} for p in w["direct_writes"]]} for w in report["writers"]], "engineering": report["engineering"]}, indent=2))
