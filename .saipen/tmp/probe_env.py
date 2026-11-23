import sys, json
sys.path.insert(0, 'C:/Users/vac34/AppData/Local/saipen/scheduled-source/tools')
from saipen_engine.test_runner import TestFamily, family_environment, identity_environment
import hashlib
env = family_environment(TestFamily('identity', (sys.executable,), 1))
ident = identity_environment(env)
print(json.dumps({'digest': hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()[:20], 'n': len(ident), 'tools': {k: v for k, v in sorted(ident.items()) if k in ('PATH', 'SystemRoot', 'SystemDrive', 'PATHEXT', 'COMSPEC')}}))
