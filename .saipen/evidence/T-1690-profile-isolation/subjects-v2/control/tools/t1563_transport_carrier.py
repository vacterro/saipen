"""The exact ordinary-import attack, with one pre/post admission oracle.

This carrier does not run a host hook, supply a secret, patch the subject, or
replace establish with a test double. The vulnerable subject is frozen bytes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run(subject_dir: Path, *, project: Path, authority: Path, home: Path) -> dict:
    tools = Path(__file__).resolve().parent
    code = f"""
import sys, json
from pathlib import Path
sys.path.insert(0, {str(tools)!r})
sys.path.insert(0, {str(subject_dir)!r})
import protocol_admission as pa
pa.__package__ = 'saipen_engine'
ctx = pa.Context(project_root=Path({str(project)!r}), session_id='attack-session',
    host='claude', model='model-a', provider='provider-a',
    authority_root=Path({str(authority)!r}), home=Path({str(home)!r}),
    adapters={{'claude': {{'admission_enforcement': 'MECHANICAL',
        'instruction_surfaces': ['~/.claude/CLAUDE.md']}}}})
before = pa.evaluate(ctx)['state']
try:
    key = pa.bootstrap_transport_key(ctx.project_root)
    mac = pa._transport_mac(key, 'establish', 'UserPromptSubmit', ctx.session_id)
    cap = 'hook:UserPromptSubmit:' + mac
    result = pa.establish(ctx, transport=cap)
    error = None
except (AttributeError, PermissionError) as exc:
    result = {{'state': 'REFUSED', 'permitted': False}}
    error = type(exc).__name__
after = pa.evaluate(ctx)['state']
print(json.dumps({{'before': before, 'result': result['state'], 'after': after,
    'admitted': after == 'ADMITTED', 'error': error}}))
"""
    process = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        encoding="utf-8",
        check=False,
        env={key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")},
    )
    if process.returncode:
        raise RuntimeError(process.stderr)
    return json.loads(process.stdout)
