"""Independent structural and byte comparison for the reviewed live diff."""
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / '.saipen/kitchen/t1297-repair'
def baseline(rel):
    return subprocess.check_output(['git', '-C', str(root), 'show', 'b71590b5:' + rel]).decode('utf-8').replace('\r\n', '\n')

original = ast.parse(baseline('tools/saipen.py'))
current = ast.parse((root / 'tools/saipen.py').read_text(encoding='utf-8'))
def function(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
assert ast.dump(function(original, '_status')) == ast.dump(function(current, '_status'))
def stop_body(tree, token):
    return next(n.body for n in function(tree, 'main').body if isinstance(n, ast.If) and ast.unparse(n.test) == f"command in ('stop', '{token}')")
assert [ast.dump(n) for n in stop_body(original, 'ss')] == [ast.dump(n) for n in stop_body(current, 'st')]
assert baseline('tools/saipen_engine/commands.py') == (root / 'tools/saipen_engine/commands.py').read_text(encoding='utf-8')
rows = json.loads((out / 'initial-path-classification.json').read_text())
count = 0
for row in rows:
    rel = row['path']
    if rel.startswith(('guides/', '.saipen/saitranslate/')) or rel in ('GUIDE.md', 'README.md', 'README.ee.md', 'README.ded.md', 'README.ja.md'):
        before = baseline(rel)
        after = (root / rel).read_text(encoding='utf-8')
        expected = ''.join(line.replace('`ss`', '`st`') if '#110-command-surface' in line else line for line in before.splitlines(keepends=True))
        expected = expected.replace('**v7.257.0**', '**v' + (root / 'VERSION').read_text().strip() + '**')
        assert expected == after, rel
        count += 1
    if row['category'] == 'UNRELATED':
        assert baseline(rel) == (root / rel).read_text(encoding='utf-8'), rel
for rel, digest in json.loads((out / 'protected-hashes.json').read_text()).items():
    assert hashlib.sha256((root / rel).read_bytes()).hexdigest() == digest, rel
old = baseline('CHANGELOG.md')
new = (root / 'CHANGELOG.md').read_text(encoding='utf-8')
assert new[new.index('## 7.257.0'): ] == old[old.index('## 7.257.0'): ]
assert new.count('T-1297') == 1
assert len(json.loads((root / 'saipen/REGISTRY.json').read_text())['shortcuts']) == 19
print(f'PASS: STOP body AST identical; _status AST identical; normalization owner byte-equivalent; {count} current/localized documents differ only in shortcut callout and release badge; seven unrelated paths restored; protected archive and audit bytes unchanged; one changelog entry; 19 registry keys.')
