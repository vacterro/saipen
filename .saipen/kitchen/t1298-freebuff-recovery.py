"""Preserve exact runtime tool payloads from this project's local history."""
import json
import sqlite3
from pathlib import Path

db = 'file:C:/Users/vac34/.config/freebuff-desktop/projects/_SAIPEN-a3407352-5f8d-4360-a144-d4093d6694a6/desktop-v2.db?mode=ro'
c = sqlite3.connect(db, uri=True)
rows = c.execute("select seq,parts_json from messages where seq >= 286 and role = 'assistant'").fetchall()
out = Path('.saipen/kitchen/t1298-recovery/freebuff-history')
out.mkdir(exist_ok=True)
for seq, data in rows:
    (out / f'{seq}.json').write_text(data, encoding='utf-8')
    parts = json.loads(data)
    for i, part in enumerate(parts):
        if part.get('kind') == 'changes':
            print('change set', seq, i, [(x['path'], x.get('adds'), x.get('dels')) for x in part['files']])
print(json.dumps({'matches':[(seq,len(data)) for seq,data in rows]}))
