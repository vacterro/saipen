import sys
sys.path.insert(0, 'tools')
from pathlib import Path
from saipen_engine.isolated_release import recorded_staging_survival

s = recorded_staging_survival(Path('.'), '.saipen/evidence/index-forensics/staged_manifest_20261102.json')
print('recorded', s['recorded_count'], 'live', s['live_staged_count'])
print('lost', s['content_lost_paths'])
inplace = [m for m in s['relocated_detail'] if m['live_sha'] != '(relocated/retired)']
print('in-place changed', len(inplace))
for m in inplace:
    print('  ', m['path'], m['recorded_sha'], '->', m['live_sha'])
