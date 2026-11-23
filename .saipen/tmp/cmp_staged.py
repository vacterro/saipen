import json, subprocess, os

SEP = chr(92)
d = json.load(open('.saipen/evidence/index-forensics/staged_manifest_20261102.json'))
old = set()
for e in d['entries']:
    if isinstance(e, dict):
        p = e.get('path') or e.get('name')
    else:
        p = str(e)
    if p:
        old.add(p.replace(SEP, '/'))
print('manifest paths', len(old))
cur_raw = subprocess.run(['git', 'diff', '--cached', '--name-only'], capture_output=True, text=True).stdout.splitlines()
cur = {c.replace(SEP, '/') for c in cur_raw if c.strip()}
print('current staged', len(cur))
new = sorted(cur - old)
print('newly staged (not in manifest):', len(new))
for p in new[:500]:
    print('  +', p)
gone = sorted(old - cur)
print('gone from index:', len(gone))
for p in gone[:30]:
    print('  -', p)
