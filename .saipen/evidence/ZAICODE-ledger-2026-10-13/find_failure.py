"""Find only the reported ledger failure in read-only OpenCode tool records."""
import json
from pathlib import Path
import sqlite3

path = Path("C:/Users/vac34/.local/share/opencode/opencode.db")
connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)
connection.execute("PRAGMA query_only = ON")
tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
if "part" not in tables:
    print(json.dumps({"tables": sorted(tables)}))
else:
    columns = [r[1] for r in connection.execute("PRAGMA table_info(part)")]
    print(json.dumps({"part_columns": columns}))
    if "data" in columns:
        matches = connection.execute(
            "SELECT id, session_id, data FROM part WHERE instr(data, ?) > 0 LIMIT 20",
            ("E-3134 parent E-3133",),
        ).fetchall()
        records = []
        for part, session, raw in matches:
            data = json.loads(raw)
            state = data.get("state") or {}
            output = str(state.get("output") or state.get("error") or "")
            if data.get("type") != "tool" or "HISTORY_LEDGER_CORRUPT" not in output:
                continue
            position = output.index("HISTORY_LEDGER_CORRUPT")
            records.append({"part": part, "session": session, "tool": data.get("tool"),
                            "time": state.get("time"), "input": state.get("input"),
                            "error_excerpt": output[max(0, position - 80):position + 900]})
        result = {"database": str(path), "matching_rows": len(matches), "tool_failures": records}
        (Path(__file__).parent / "host-failure-records.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
connection.close()
