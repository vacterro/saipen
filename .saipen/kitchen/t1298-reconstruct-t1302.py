"""Reconstruct historical code from exact captured diffs, outside the candidate."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

root = Path.cwd()
evidence = root / '.saipen/kitchen/t1298-recovery'
out = evidence / 't1302-reconstructed'
out.mkdir(exist_ok=True)

def normalized(raw):
    return raw.decode('utf-8-sig').replace('\r\n', '\n')

def apply_exact(text, patch):
    lines = text.splitlines(keepends=True)
    chunks = re.split(r'(?m)^@@ -([0-9]+)(?:,[0-9]+)? \+[0-9]+(?:,[0-9]+)? @@[^\n]*\n', patch)
    cursor = 0
    for i in range(1, len(chunks), 2):
        old, new = [], []
        for line in chunks[i + 1].splitlines(keepends=True):
            if line.startswith((' ', '-')):
                old.append(line[1:])
            if line.startswith((' ', '+')):
                new.append(line[1:])
        matches = [j for j in range(cursor, len(lines) - len(old) + 1) if lines[j:j+len(old)] == old]
        if not old:
            matches = [int(chunks[i])]
        if len(matches) != 1:
            raise ValueError(f'hunk {chunks[i]} has {len(matches)} exact matches')
        start = matches[0]
        lines[start:start+len(old)] = new
        cursor = start + len(new)
    return ''.join(lines)

report = []
for seq in (286, 294):
    parts = json.loads((evidence / 'freebuff-history' / f'{seq}.json').read_text())
    files = [f for part in parts if part.get('kind') == 'changes' for f in part['files']]
    for f in files:
        rel = f['path'].replace('\\', '/')
        assert not rel.startswith('/') and '..' not in Path(rel).parts
        patch = f.get('patch', '')
        patch_path = out / 'patches' / str(seq) / (rel + '.patch')
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(patch, encoding='utf-8')
        candidates = []
        for source in [out / 'files' / rel, evidence / 'worktree' / rel]:
            if source.is_file():
                candidates.append((str(source.relative_to(root)), normalized(source.read_bytes())))
        backup_name = {'tools/saipen.py':'saipen.py.foreign', 'tools/validate.py':'validate.py.foreign', 'tools/saipen_engine/operations.py':'operations.py.foreign'}.get(rel)
        if backup_name:
            source = root / '.saipen/kitchen/t1298-review-foreign-backup' / backup_name
            if source.exists():
                candidates.append((str(source.relative_to(root)), normalized(source.read_bytes())))
        head = subprocess.run(['git', 'show', 'HEAD:' + rel], capture_output=True)
        if head.returncode == 0:
            candidates.append(('HEAD:' + rel, normalized(head.stdout)))
        else:
            candidates.append(('absent', ''))
        errors = []
        for name, base in candidates:
            try:
                result = apply_exact(base, patch)
            except ValueError as exc:
                errors.append(f'{name}: {exc}')
                continue
            target = out / 'files' / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(result.encode())
            report.append({'seq':seq, 'path':rel, 'base':name, 'sha256':hashlib.sha256(result.encode()).hexdigest()})
            break
        else:
            report.append({'seq':seq, 'path':rel, 'unresolved':errors})
(out / 'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
