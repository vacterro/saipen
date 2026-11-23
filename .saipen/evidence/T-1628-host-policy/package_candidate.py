import difflib
import hashlib
import json
import shutil
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
draft = Path(json.loads((evidence / 'scratch.json').read_text())['project'])
paths = json.loads((evidence / 'paths.json').read_text())
baseline = json.loads((evidence / 'baseline.json').read_text())
patch = []
candidate_hashes = {}
for relative in paths:
    live = root / relative
    current = hashlib.sha256(live.read_bytes()).hexdigest() if live.is_file() else None
    if current != baseline[relative]:
        raise SystemExit(f'live baseline changed; stop integration: {relative}')
    source = draft / relative
    target = evidence / 'candidate' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    candidate_hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    saved = evidence / 'pre' / relative
    before = saved.read_text(encoding='utf-8-sig').splitlines(keepends=True) if saved.is_file() else []
    after = source.read_text(encoding='utf-8-sig').splitlines(keepends=True)
    patch.extend(difflib.unified_diff(before, after, fromfile='a/' + relative,
                                      tofile='b/' + relative))
(evidence / 'owned-review.patch').write_text(''.join(patch), encoding='utf-8')
(evidence / 'candidate.json').write_text(json.dumps(candidate_hashes, indent=2) + '\n',
                                        encoding='utf-8')
print(json.dumps({'paths': len(paths), 'candidate': str(evidence / 'candidate')}))
