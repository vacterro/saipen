import hashlib
import json
import shutil
import sys
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
draft = Path(json.loads((evidence / 'scratch.json').read_text())['project'])
for relative in ('bootstrap/inject.ps1', 'bootstrap/inject.sh',
                 'tools/test_t1683_launcher_profile.py'):
    shutil.copyfile(root / relative, draft / relative)
sys.path.insert(0, str(root / 'tools'))
from saipen_engine.test_runner import _ignore_copy
from saipen_engine.core_unit import FINGERPRINT_EXCLUDED, tree_fingerprint
import os


def subject_paths(base):
    paths = {}
    for directory, directories, files in os.walk(base):
        here = Path(directory)
        ignored = _ignore_copy(directory, [*directories, *files])
        if here == base:
            ignored |= set(FINGERPRINT_EXCLUDED)
        directories[:] = [name for name in directories if name not in ignored]
        for name in files:
            path = here / name
            if name not in ignored and path.is_file():
                paths[path.relative_to(base).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return paths


live = subject_paths(root)
candidate = subject_paths(draft)
owned = set(json.loads((evidence / 'paths.json').read_text()))
unexpected = sorted(path for path in set(live) | set(candidate)
                    if path not in owned and live.get(path) != candidate.get(path))
result = {'unexpected_differences': unexpected, 'candidate_fingerprint': tree_fingerprint(draft),
          'live_fingerprint': tree_fingerprint(root), 'paths': len(candidate)}
(evidence / 'private-subject.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
raise SystemExit(bool(unexpected))
