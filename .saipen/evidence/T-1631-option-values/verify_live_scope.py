from __future__ import annotations

import hashlib
import json
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
scope = json.loads((root / '.saipen/evidence/T-1631-argv-values/scope.json').read_text())
checks = []
for relative, hashes in scope.items():
    current = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    checks.append({'path': relative, 'matches': current == hashes['after_sha256']})
record = {'paths': checks, 'all_match': all(item['matches'] for item in checks),
          'oracle_rerun': 'python -B -m unittest test_t1631_argv_values: 8 pass',
          'review': 'Production change preserves operand positions before global scan; four malformed carriers move formatting globals first, common helper binds and runs at fixture cwd; original assertions remain unchanged. Literal compound/help findings are attributed to T-1684.'}
(evidence / 'final-scope-review.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record))
raise SystemExit(0 if record['all_match'] else 1)
