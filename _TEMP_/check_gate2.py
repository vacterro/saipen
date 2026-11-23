import json, sys
sys.path.insert(0, 'tools')
from pathlib import Path
from saipen_engine import regression_execution as re2
root = Path('.').resolve()
rec = json.load(open('.saipen/evidence/regression/regression-execution-0f33a43263b748e29c23514eee5e3107.json'))
mat = re2._load(root, root / rec['contract_path'])
print('verifier recomputed:', mat['verifier'][:16])
print('verifier recorded  :', rec['after']['verifier'][:16])
print('MATCH' if mat['verifier'] == rec['after']['verifier'] else 'MISMATCH')
