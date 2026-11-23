"""Non-destructive write-access probe executed inside the existing OS sandbox."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGETS = [
    '.saipen/STATE.md', '.saipen/BOARD.md', '.saipen/LOG.md', '.saipen/IDENTITY.md',
    '.saipen/intake/index.json', '.saipen/intake/audit_inbox.json',
    '.saipen/intake/active/SRC-216.md', '.saipen/intake/active/SRC-217.md',
    'tools/saipen_engine/operations.py', 'tools/saipen.py',
    'audit/SAIPEN_20261010_1202.md', 'audit/SAIPEN_20261011_1832.md',
    'audit/SAIPEN_20261011_1901.md', 'VERSION',
]


def attempt(rel):
    path = ROOT / rel
    before = path.read_bytes()
    try:
        # Request write access only: no truncate, append, write, chmod or deletion.
        fd = os.open(path, os.O_WRONLY)
    except PermissionError as exc:
        denied = True
        error = str(exc)
    else:
        os.close(fd)
        denied = False
        error = 'WRITE ACCESS WAS ALLOWED; boundary is not admitted'
    after = path.read_bytes()
    return {'path': rel, 'read_ok': True, 'sha256': hashlib.sha256(before).hexdigest(),
            'write_access_denied': denied, 'error': error, 'bytes_unchanged': before == after}


if len(sys.argv) > 1 and sys.argv[1] == 'child':
    result = attempt('tools/saipen.py')
    print(json.dumps(result))
    raise SystemExit(0 if result['write_access_denied'] and result['bytes_unchanged'] else 1)
results = [attempt(rel) for rel in TARGETS]
child = subprocess.run([sys.executable, '-B', __file__, 'child'], capture_output=True, timeout=15)
record = {'kind': 'real_os_read_write_access_probe', 'targets': results,
          'child_exit_code': child.returncode, 'child_stdout': child.stdout.decode('utf-8', 'replace'),
          'child_stderr': child.stderr.decode('utf-8', 'replace'),
          'writes_performed': 0,
          'pass': all(r['write_access_denied'] and r['bytes_unchanged'] for r in results) and child.returncode == 0,
          'limit': 'Actual OS write-open refusal at listed targets, including child inheritance. No model evaluation yet.'}
print(json.dumps(record, indent=2))
raise SystemExit(0 if record['pass'] else 1)
