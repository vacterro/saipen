import json, sys
sys.path.insert(0, 'tools')
from pathlib import Path
import importlib
re_mod = importlib.import_module('saipen_engine.regression_execution')
root = Path('.').resolve()
rec = json.load(open('.saipen/evidence/regression/regression-execution-e5a7b84dffcd42b2bb1d1ce3ee5daf1d.json'))
mat = re_mod._load(root, root / rec['contract_path'])
print('verifier match:', mat['verifier'] == rec['after']['verifier'])
print('verifier now :', mat['verifier'][:16], ' recorded:', rec['after']['verifier'][:16])
print('prior match  :', re_mod._sha(re_mod._json(re_mod._manifest(mat['prior']))) == rec['before']['subject'])
print('context match:', re_mod._sha(re_mod._json(re_mod._manifest(mat['context']))) == rec['context_digest'])
print('current match:', re_mod._sha(re_mod._json(re_mod._manifest(mat['current']))) == rec['after']['subject'])
# decompose verifier: command/format/timeout/runtime/oracle/env
c = json.loads(open(rec['contract_path']).read())
import os, hashlib
from saipen_engine import regression_execution as re2
runtime, argv, env = re2._runtime(c['command'])
parts = {
 'command': c['command'], 'format': c['format'], 'timeout': c['timeout'],
 'runtime': {**runtime, 'path': os.path.normcase(runtime['path'])},
 'oracle': {k: re2._sha(mat['context'][k]) for k in re2._paths(c['oracle_files'])},
 'environment_digest': re2._sha(re2._json(env)),
}
v = re2._sha(re2._json(parts))
print('recomputed verifier:', v[:16])
# what's in the recorded environment?
json.dump({'env_keys': sorted(env.keys()), 'runtime': parts['runtime'], 'oracle': parts['oracle']}, open('_TEMP_/gate_debug.json','w'), indent=1)
print('env var count:', len(env))
