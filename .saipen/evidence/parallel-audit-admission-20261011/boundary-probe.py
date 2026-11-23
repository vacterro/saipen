"""One-off host admission observation; never a worker or a new runtime owner."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent


def snapshot():
    paths = [ROOT / '.saipen' / name for name in ('STATE.md', 'BOARD.md', 'LOG.md', 'IDENTITY.md')]
    paths += sorted((ROOT / 'audit').glob('*.md'))
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


label, mode = sys.argv[1:]
target = OUT / (label + '.json')
if target.exists():
    raise SystemExit('immutable observation already exists')
before = snapshot()
command = ['C:/nodejs/codex.cmd', '-c', 'windows.sandbox=' + mode, 'sandbox',
           '--include-managed-config', '--permission-profile', ':read-only', '--',
           'cmd.exe', '/d', '/c', 'echo READ_ONLY_SANDBOX_STARTUP_OK']
started = datetime.now(timezone.utc).isoformat()
t0 = time.monotonic()
try:
    run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=45)
    result = {'exit_code': run.returncode, 'stdout': run.stdout.decode('utf-8', 'replace'),
              'stderr': run.stderr.decode('utf-8', 'replace'), 'timed_out': False}
except subprocess.TimeoutExpired as exc:
    result = {'exit_code': None, 'stdout': (exc.stdout or b'').decode('utf-8', 'replace'),
              'stderr': (exc.stderr or b'').decode('utf-8', 'replace'), 'timed_out': True}
after = snapshot()
record = {'kind': 'sandbox_startup_probe', 'started_utc': started, 'command': command,
          'elapsed_seconds': round(time.monotonic() - t0, 3), **result,
          'before': before, 'after': after, 'canonical_and_audit_unchanged': before == after,
          'worker_started': False, 'write_refusal_proved': False,
          'limit': 'Startup only. Even success does not prove denied writes or admit Stage A.'}
target.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, indent=2))
raise SystemExit(0 if result['exit_code'] == 0 and before == after else 1)
