import json
import subprocess

man = json.load(open('.saipen/evidence/index-forensics/staged_manifest_20261102.json'))
gone = []
for e in man['entries']:
    sha = e.get('blob_sha') or ''
    if len(sha) < 8:
        gone.append((e['path'], sha, 'short'))
        continue
    if len(sha) < 40:
        out = subprocess.run(['git', 'rev-parse', '--disambiguate=' + sha],
                             capture_output=True, text=True).stdout.strip()
        ok = bool(out)
    else:
        ok = subprocess.run(['git', 'cat-file', '-e', sha],
                            capture_output=True).returncode == 0
    if not ok:
        gone.append((e['path'], sha[:8], 'ABSENT'))
print('entries', len(man['entries']), 'recorded blobs absent from object db:', len(gone))
for g in gone[:25]:
    print(' ', g)
