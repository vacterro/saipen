"""Read-only search for exact T-1302 runtime edits in this project's journal."""
import json
import sqlite3
from pathlib import Path

c = sqlite3.connect('file:C:/Users/vac34/.local/share/opencode/opencode.db?mode=ro', uri=True)
rows = c.execute('select p.id,p.data from part p join session s on s.id=p.session_id where s.project_id=? and (p.data like ? or p.data like ?)', ('13de01f5617375515e5f22b3c7cee7e0ede42a58', '%def is_user_explicit(%', '%def user_request(%')).fetchall()
out = Path('.saipen/kitchen/t1298-recovery/runtime-journal')
out.mkdir(exist_ok=True)
for key, data in rows:
    (out / (key + '.json')).write_text(data, encoding='utf-8')
print(json.dumps({'matching_parts': [(key, len(data)) for key, data in rows]}))
