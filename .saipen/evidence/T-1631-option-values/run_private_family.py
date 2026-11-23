import json
import shutil
import sys
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
draft = Path(json.loads((evidence / 'scratch.json').read_text())['project'])
sys.path.insert(0, str(draft / 'tools'))
from saipen_engine.core_unit import run_family, tree_fingerprint, write_record
from saipen_engine.inflight import holding

before = tree_fingerprint(draft)
with holding(draft, 'T-1631', 'isolated candidate core-unit family'):
    run = run_family(draft, jobs=6)
    written = write_record(draft, run, run.get('fingerprint') or before)
after = tree_fingerprint(draft)
unchanged = before == after == written['record']['fingerprint']
record = written['record']
result = {'fingerprint': record['fingerprint'], 'verdict': record['verdict'],
          'ran': record['ran'], 'red': record['red'], 'problems': record['problems'],
          'record': written['path'], 'sha256': written['sha256'], 'unchanged': unchanged,
          'sandboxes_leaked': record.get('sandboxes_leaked'),
          'processes_leaked': record.get('processes_leaked')}
if unchanged:
    destination = root / written['path']
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(draft / written['path'], destination)
(evidence / 'private-family.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
raise SystemExit(0 if unchanged and record['verdict'] == 'PASS' else 1)
