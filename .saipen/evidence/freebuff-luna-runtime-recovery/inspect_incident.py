"""Read the independently bound Freebuff project history without invoking its engine."""
import datetime
import json
import sqlite3
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
DATABASE = Path('C:/Users/vac34/.config/freebuff-desktop/projects/_FREEBUFF_SAI-7e6b2250-09e1-4fd5-b3d6-2e599c580037/desktop-v2.db')
connection = sqlite3.connect(DATABASE.as_uri() + '?mode=ro', uri=True)
connection.execute('PRAGMA query_only = ON')
connection.row_factory = sqlite3.Row
needles = ('ENOENT', 'SAIPEN_HOST_RUNTIME_UNAVAILABLE', 'read-before-lock', 'read before lock')
records = []
with connection:
    for row in connection.execute('''
        SELECT m.seq, m.thread_id, m.role, m.ts, m.parts_json,
               t.title, t.model, t.project_path, t.worktree_path, t.execution_mode, t.sponsored
        FROM messages AS m JOIN threads AS t ON t.id = m.thread_id
        WHERE m.thread_id = '96ba4e8c-ef79-47c2-9e91-d2aad7c7096d' AND m.seq >= 81
        ORDER BY m.seq
    '''):
        data = dict(row)
        parts = json.loads(data.pop('parts_json'))
        strings = []
        def visit(value, key=''):
            if isinstance(value, str) and any(n.lower() in value.lower() for n in needles):
                indexes = [value.lower().find(n.lower()) for n in needles if n.lower() in value.lower()]
                start = max(0, min(indexes) - 700)
                strings.append({'field': key, 'offset': start, 'text': value[start:start + 8000]})
            elif isinstance(value, dict):
                for k, v in value.items():
                    visit(v, key + '.' + k)
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    visit(v, key + '[' + str(i) + ']')
        visit(parts)
        data['matches'] = strings
        data['tools'] = [p for p in parts if isinstance(p, dict) and p.get('toolName') == 'run_terminal_command']
        data['part_shapes'] = [{k: p.get(k) for k in ('type', 'kind', 'toolName', 'name') if k in p}
                               for p in parts if isinstance(p, dict)]
        records.append(data)
connection.close()
result = {'readonly': True, 'database': str(DATABASE), 'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'records': records}
(EVIDENCE / 'incident-history.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'records': [{**{k: v for k, v in r.items() if k not in ('matches', 'part_shapes')},
                              'matches': [m for m in r['matches'] if len(m['text']) < 2000]}
                             for r in records]}, ensure_ascii=True, indent=2))
