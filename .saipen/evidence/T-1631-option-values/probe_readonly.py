import json
import os
import sys
import tempfile
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
sys.path.insert(0, str(root / 'tools'))
from test_guard_hostile_matrix import fresh_project
from saipen_engine.process_tree import run

results = []
with tempfile.TemporaryDirectory(prefix='saipen-t1631-readonly-') as tmp:
    home = Path(tmp) / 'home'
    home.mkdir()
    env = {key: value for key, value in os.environ.items() if not key.startswith('SAIPEN_')}
    env.update(HOME=str(home), USERPROFILE=str(home), HOMEDRIVE='', HOMEPATH='',
               CLAUDE_CONFIG_DIR='', SAIPEN_CAPABILITY='read-only',
               SAIPEN_MACHINE_ROOT=str(home / 'no-machine-runtime'))
    for value in ('ordinary proof', '--help'):
        project = fresh_project()
        board = project / '.saipen/BOARD.md'
        before = board.read_bytes()
        proc = run([sys.executable, '-B', str(root / 'tools/saipen.py'),
                    '--project-root', str(project), '--json', 'ticket', 'add', 'P3',
                    'Read-only argument control', '--verify', value],
                   cwd=root, env=env, capture_output=True, text=True,
                   encoding='utf-8', errors='replace', timeout=30)
        results.append({'value': value, 'rc': proc.returncode,
                        'result': json.loads(proc.stdout), 'board_changed': before != board.read_bytes()})
(evidence / 'readonly-probe.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
print(json.dumps(results))
