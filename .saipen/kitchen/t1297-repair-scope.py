"""Bounded continuation inventory and preservation; not a release tool."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / '.saipen/kitchen/t1297-repair'
out.mkdir(exist_ok=True)

def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args])

paths = git('diff', '--name-only', '-z').decode().strip('\0').split('\0')
rows = []
for rel in paths:
    if rel.startswith('.saipen/extensions/subs/'):
        category = 'UNRELATED'
    elif rel.startswith('.saipen/intake/') or rel in ('.saipen/STATE.md', '.saipen/BOARD.md', '.saipen/LOG.md'):
        category = 'SAIPEN_JOURNAL_STATE'
    elif rel == 'tools/saipen.py':
        category = 'REQUIRED_RUNTIME'
    elif rel in ('saipen/REGISTRY.json', 'tools/validate.py'):
        category = 'REQUIRED_MACHINE_CONTRACT'
    elif rel.startswith('tools/test_'):
        category = 'REQUIRED_TEST'
    elif rel.startswith('tests/') or rel == 'saipen/CONFORMANCE.md':
        category = 'REQUIRED_CONFORMANCE'
    elif rel.startswith(('.saipen/saitranslate/', 'guides/')) or rel in ('README.ee.md', 'README.ded.md', 'README.ja.md'):
        category = 'REQUIRED_GENERATED_OR_LOCALIZED_SURFACE'
    else:
        assert rel in ('GUIDE.md', 'README.md', 'bootstrap/inject.ps1', 'bootstrap/inject.sh', 'saipen/COMMANDS.md', 'saipen/SKILL.md'), rel
        category = 'REQUIRED_CURRENT_DOC'
    rows.append({'path': rel, 'category': category})
    if category == 'UNRELATED':
        source = root / rel
        backup = out / 'preserved-unrelated' / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        assert not backup.exists(), backup
        backup.write_bytes(source.read_bytes())
        source.write_bytes(git('show', 'HEAD:' + rel))

(out / 'initial-path-classification.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
golden = root / 'tests/protocol_semantic_golden.json'
before = git('show', 'HEAD:tests/protocol_semantic_golden.json')
narrow = before.replace(b'"ss": [', b'"st": [', 1)
assert json.loads(narrow) == json.loads(golden.read_bytes()), 'Golden contains another semantic change'
(out / 'golden-before-narrowing.json').write_bytes(golden.read_bytes())
golden.write_bytes(narrow)
protected = git('ls-files', '-z', 'CHANGELOG_ARCHIVE*', '.saipen/archive').decode().strip('\0').split('\0')
protected += [f'audit/{n}.md' for n in range(11, 16)]
hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in protected if p and (root / p).is_file()}
(out / 'protected-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
print('Classified', len(rows), 'tracked changed paths; preserved/restored', sum(r['category'] == 'UNRELATED' for r in rows), 'unrelated paths; golden semantic equality proven.')
