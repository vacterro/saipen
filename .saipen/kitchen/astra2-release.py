"""Run the canonical release with a separate index; preserve foreign staging."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
KITCHEN = ROOT / '.saipen/kitchen'
SCOPE = [
    'tools/saipen.py',
    'tools/saipen_engine/conformance.py',
    'tools/saipen_engine/conformance_lineage.py',
    'tools/saipen_engine/controls.py',
    'tools/saipen_engine/convergence.py',
    'tools/saipen_engine/findings.py',
    'tools/saipen_engine/journal.py',
    'tools/saipen_engine/operations.py',
    'tools/saipen_engine/producer_gate.py',
    'tools/saipen_engine/release.py',
    'tools/saipen_engine/settled_projection.py',
    'tools/test_conformance_lineage.py',
    'tools/test_settled_projection.py',
    'tools/test_source_receipts.py',
    'tools/test_validator_findings.py',
    'tools/validate.py',
]

def git(*args, env=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=env)

index = Path(git('rev-parse', '--git-path', 'index').decode().strip()).resolve()
alt = index.with_name('astra2-T1298.index')
env = dict(os.environ, GIT_INDEX_FILE=str(alt))
action = sys.argv[1]
if action == 'prepare':
    assert not alt.exists(), 'Existing release index must be resumed, never overwritten'
    (KITCHEN / 'astra2-default-index.backup').write_bytes(index.read_bytes())
    (KITCHEN / 'astra2-default-index-entries').write_bytes(git('ls-files', '-s', '-z'))
    git('read-tree', 'HEAD', env=env)
    git('add', '--', *SCOPE, env=env)
    assert Path(git('rev-parse', '--git-path', 'index', env=env).decode().strip()).resolve() == alt
    print(json.dumps({'index': str(alt), 'scope': SCOPE}))
elif action in ('scope', 'plan', 'ship'):
    args = ['scope', 'T-1298', *SCOPE] if action == 'scope' else ['ship']
    if action == 'plan':
        args.append('--dry-run')
    result = subprocess.run([sys.executable, 'tools/saipen.py', *args, '--json'], env=env)
    raise SystemExit(result.returncode)
else:
    raise SystemExit('Unknown action')
