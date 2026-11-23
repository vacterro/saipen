import json, collections
SEP = chr(92)
d = json.load(open('.saipen/evidence/index-forensics/staged_manifest_20261102.json'))
print('keys', list(d.keys()))
print('head', d.get('head'), 'branch', d.get('branch'))
print('index_metadata', json.dumps(d.get('index_metadata'))[:400])
print('classification_summary', d.get('classification_summary'))
ents = d['entries']
print('entries', len(ents))
print('sample entry', json.dumps(ents[0])[:300])
c = collections.Counter()
for e in ents:
    p = e['path'].replace(SEP, '/')
    parts = p.split('/')
    key = parts[0] + '/' + (parts[1] if len(parts) > 1 else '')
    c[key] += 1
for k, v in c.most_common(25):
    print(f'  {v:5d}  {k}')
