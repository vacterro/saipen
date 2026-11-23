from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
scratch = Path(tempfile.mkdtemp(prefix='saipen-t1628-draft-'))
draft = scratch / 'project'
sys.path.insert(0, str(root / 'tools'))
from saipen_engine.test_runner import _ignore_copy


def ignore(directory, names):
    extra = {'.saipen'} if Path(directory) == root else set()
    return _ignore_copy(directory, names) | {name for name in names if name in extra}


shutil.copytree(root, draft, symlinks=True, ignore=ignore)
paths = [
    'extensions/adapters/opencode/saipen-guard.js',
    'extensions/adapters/opencode.md',
    'extensions/adapters/registry.json',
    'tools/saipen_engine/native_host_policy.py',
    'tools/test_t1628_opencode_policy.py',
    'tools/test_opencode_adapter.py',
    'tools/test_continue_entry.py',
    'tools/test_t1624_host_integration.py',
]
baseline = {}
for relative in paths:
    path = root / relative
    if path.is_file():
        saved = evidence / 'pre' / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, saved)
        baseline[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        baseline[relative] = None
(evidence / 'scratch.json').write_text(json.dumps({'scratch': str(scratch), 'project': str(draft)}, indent=2) + '\n', encoding='utf-8')
(evidence / 'paths.json').write_text(json.dumps(paths, indent=2) + '\n', encoding='utf-8')
(evidence / 'baseline.json').write_text(json.dumps(baseline, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'project': str(draft), 'paths': len(paths)}))
