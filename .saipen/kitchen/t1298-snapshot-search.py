"""Recover exact runtime blobs from the project-specific editor snapshot."""
import json
import subprocess
from pathlib import Path

git = ['git', '--git-dir=C:/Users/vac34/.local/share/opencode/snapshot/13de01f5617375515e5f22b3c7cee7e0ede42a58/2778d0bc6299d3823dfcb372f2c7838b0cbeef22']
rows = subprocess.check_output(git + ['cat-file', '--batch-all-objects', '--batch-check']).splitlines()
out = Path('.saipen/kitchen/t1298-recovery/editor-snapshot')
out.mkdir(exist_ok=True)
p = subprocess.Popen(git + ['cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
matches = []
count = 0
for row in rows:
    oid, kind, size = row.split()
    if kind != b'blob' or not 1000 < int(size) < 1000000:
        continue
    count += 1
    p.stdin.write(oid + b'\n')
    p.stdin.flush()
    header = p.stdout.readline().split()
    data = p.stdout.read(int(header[2]))
    assert p.stdout.read(1) == b'\n'
    if b'def is_user_explicit(' in data or b'def user_request(' in data or (b'INHERITED_VERIFIED' in data and b'def ' in data):
        (out / oid.decode()).write_bytes(data)
        matches.append({'oid': oid.decode(), 'bytes':len(data)})
p.stdin.close()
p.wait()
(out / 'manifest.json').write_text(json.dumps({'scanned':count,'matches':matches}, indent=2), encoding='utf-8')
print(json.dumps({'scanned':count,'matches':matches}))
