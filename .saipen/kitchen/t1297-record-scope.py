"""Record only reviewed T-1297 paths using the canonical operation."""
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'tools'))
from saipen_engine.release_contract import source_authority_paths

def git(*args):
    return subprocess.check_output(['git', '-c', 'core.safecrlf=false', '-C', str(root), *args]).decode()

paths = set(filter(None, git('diff', '--name-only', '-z').split('\0')))
assert not any(p.startswith('.saipen/extensions/subs/') for p in paths)
paths.update(p.as_posix() for p in source_authority_paths(root)
             if p.as_posix().startswith(('.saipen/intake/', '.saipen/archive/source/'))
             and 'SRC-02' in p.name and ('SRC-023' in p.name or 'SRC-024' in p.name))
paths.update([
    '.saipen/kitchen/t1297-review.md',
    '.saipen/kitchen/t1297-inspect.py',
    '.saipen/kitchen/t1297-red-control.py',
])
for name in ('initial-path-classification.json', 'protected-hashes.json',
             'inspection.log', 'focused-final.log', 'red-control.log',
             'unit-final.log', 'consumer.log', 'validator-final.log',
             'review-tests.log', 'review-validator.log', 'audit-checks.log',
             'parity.log', 'parity-final.log', 'fixture-tests.log',
             'fixture-validator.log'):
    paths.add('.saipen/kitchen/t1297-repair/' + name)
rows = []
initial = json.loads((root / '.saipen/kitchen/t1297-repair/initial-path-classification.json').read_text())
categories = {r['path']: r['category'] for r in initial}
for path in sorted(paths):
    category = categories.get(path)
    if path == 'tools/audit_checks.py':
        category = 'REQUIRED_TEST'
    if category is None:
        category = 'SAIPEN_JOURNAL_STATE' if path.startswith('.saipen/') else 'REQUIRED_MACHINE_CONTRACT' if path == 'VERSION' else 'REQUIRED_CURRENT_DOC'
    rows.append({'path': path, 'category': category})
manifest = root / '.saipen/kitchen/t1297-repair/final-path-classification.json'
manifest.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
paths.add(manifest.relative_to(root).as_posix())
assert not git('diff', '--cached', '--name-only').strip(), 'Preserve foreign staging'
result = subprocess.run([sys.executable, str(root / 'tools/saipen.py'), '--json',
                         'scope', 'T-1297', *sorted(paths)], cwd=root)
sys.exit(result.returncode)
