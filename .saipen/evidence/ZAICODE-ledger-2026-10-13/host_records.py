"""Read host metadata with SQLite's read-only URI; never open credential files."""
import json
from pathlib import Path
import sqlite3

path = Path("C:/Users/vac34/.zcode/v2/tasks-index.sqlite")
connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)
connection.execute("PRAGMA query_only = ON")
rows = connection.execute(
    "SELECT task_id, workspace_path, created_at, updated_at, meta_json, "
    "instr(searchable_text, 'HISTORY_LEDGER_CORRUPT') FROM tasks "
    "WHERE workspace_path LIKE ? ORDER BY updated_at DESC LIMIT 8", ("%ZAICODE%",)
).fetchall()
out = []
for task, workspace, created, updated, meta, error_at in rows:
    metadata = json.loads(meta)
    out.append({"task_id": task, "workspace": workspace, "created_at": created,
                "updated_at": updated, "meta_keys": list(metadata),
                "contains_error_in_searchable_text": bool(error_at)})
print(json.dumps({"database": str(path), "tasks": out}, indent=2))
connection.close()
