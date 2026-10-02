"""Apply CONTRIBUTING breaking-contract policy through the release inventory."""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'tools'))
from saipen_engine.release_contract import version_metadata_paths

previous = (root / 'VERSION').read_text().strip()
assert previous == '7.257.0', 'Re-evaluate version decision against changed baseline'
major, _minor, _patch = map(int, previous.split('.'))
version = f'{major + 1}.0.0'
updates = {}
for rel in version_metadata_paths(root):
    if rel.name.startswith('README'):
        path = root / rel
        raw = path.read_bytes()
        old = f'**v{previous}**'.encode()
        assert raw.count(old) == 1, rel
        updates[path] = raw.replace(old, f'**v{version}**'.encode(), 1)
path = root / 'CHANGELOG.md'
raw = path.read_bytes()
assert b'T-1297' not in raw
anchor = re.search(rb'(?m)^## ', raw).start()
date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
entry = (
    f'## {version} -- {date} -- Distinct STOP Shortcut (T-1297, SRC-024)\n\n'
    'STOP shortcut changes from `ss` to `st` because repeated-letter `ss`/`sss` '
    'caused STOP/STATUS ambiguity for agents. `sss` remains STATUS; old `ss` '
    'is retired fail-closed and performs no action. Long-form commands are unchanged.\n\n'
).encode()
updates[path] = raw[:anchor] + entry + raw[anchor:]
updates[root / 'VERSION'] = (version + '\n').encode()
for path, raw in updates.items():
    path.write_bytes(raw)
print(f'CONTRIBUTING.md: breaking command contract => major {previous} -> {version}; {len(updates)} canonical metadata paths')
