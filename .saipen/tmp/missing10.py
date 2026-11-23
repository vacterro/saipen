import json
import subprocess

SEP = chr(92)
man = json.load(open('.saipen/evidence/index-forensics/staged_manifest_20261102.json'))
rec = {e['path'].replace(SEP, '/'): e for e in man['entries']}
out = subprocess.run(['git', 'diff', '--cached', '--raw', '--abbrev=40'],
                     capture_output=True, text=True).stdout
live = {}
for line in out.strip().splitlines():
    if not line.strip():
        continue
    parts = line.split('\t')
    live[parts[-1].replace(SEP, '/')] = parts[0].split()
missing = sorted(set(rec) - set(live))
print('missing', len(missing))
for p in missing:
    e = rec[p]
    head = subprocess.run(['git', 'rev-parse', '--verify', f'HEAD:{p}'],
                          capture_output=True, text=True).stdout.strip()
    wt = subprocess.run(['git', 'status', '--porcelain=v1', '--', p],
                        capture_output=True, text=True).stdout.strip()
    print(p)
    print('   recorded status=%s blob=%s op=%s src=%s' % (
        e['status'], e['blob_sha'][:8], e.get('operation'), e.get('src_path')))
    print('   HEAD blob=%s   status=%s' % (head[:8] or 'absent', wt or 'clean/absent'))
