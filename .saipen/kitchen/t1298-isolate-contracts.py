"""Park reviewed foreign contract deltas; retain exact backups and index."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path.cwd().resolve()
out = root / '.saipen/kitchen/t1298-recovery'
restore = ['README.md', 'SPEC.md', 'VERSION', 'CHANGELOG.md',
           'saipen/CORE.md', 'saipen/REGISTRY.json', 'saipen/COMMANDS.md',
           'saipen/phases/done.md', 'saipen/phases/ship.md',
           'extensions/schemas/board.schema.json', 'extensions/schemas/state.schema.json']
park = ['tools/test_orchestration_repair.py', 'tools/test_public_closure_cli.py',
        'tools/test_reverify.py', 'test_debt_gate.py']
evidence = {}
for rel in restore + park:
    p = (root / rel).resolve()
    assert p.is_relative_to(root)
    original = p.read_bytes()
    backup = out / 'worktree' / rel
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        assert backup.read_bytes() == original, rel
    else:
        backup.write_bytes(original)
    evidence[rel] = {'before_sha256': hashlib.sha256(original).hexdigest()}
    if rel in restore:
        baseline = subprocess.check_output(['git', 'show', 'HEAD:' + rel])
        # Use the repository checkout newline representation.
        baseline = baseline.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        p.write_bytes(baseline)
        evidence[rel]['candidate_sha256'] = hashlib.sha256(baseline).hexdigest()
    else:
        tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', '--', rel], capture_output=True)
        assert tracked.returncode != 0, rel
        assert backup.read_bytes() == p.read_bytes()
        p.unlink()
        evidence[rel]['candidate_sha256'] = None
(out / 'contract-isolation.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
assert subprocess.check_output(['git', 'ls-files', '--stage', '-z']) == (out / 'index.entries').read_bytes()
print('Parked foreign contract/test surfaces; full Git index identities unchanged.')
