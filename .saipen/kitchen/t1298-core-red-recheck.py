import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

root = Path.cwd()
sys.path.insert(0, str(root / 'tools'))
subjects = {}
for name in ('applicability', 'operations', 'convergence', 'controls', 'crew', 'release'):
    module = importlib.import_module('saipen_engine.' + name)
    rel = 'tools/saipen_engine/' + name + '.py'
    raw = subprocess.check_output(['git', 'show', 'HEAD:' + rel])
    subjects[name] = hashlib.sha256(raw).hexdigest()
    exec(compile(raw, rel + '@HEAD', 'exec'), module.__dict__)
verifiers = {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in (
    'tools/test_crew_applicability.py', 'tools/test_hostile_wave_regressions.py')}
print('VERIFIERS', json.dumps(verifiers), flush=True)
print('PRE_FIX_SUBJECTS', json.dumps(subjects), flush=True)
for requirement, names in (
    ('R003', ['test_crew_applicability.EnumerationFailureTests']),
    ('R004', ['test_crew_applicability.DynamicImportTests']),
    ('R002', ['test_crew_applicability.StrictReleaseAuthorityTests']),
    ('R001', ['test_hostile_wave_regressions.OwnedManifestTests',
              'test_hostile_wave_regressions.ScopeIdentityTests']),
):
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print('RED_CONTROL', requirement, 'tests', result.testsRun, 'failures', len(result.failures),
          'errors', len(result.errors), 'skipped', len(result.skipped), flush=True)
    if result.wasSuccessful():
        raise SystemExit('RED CONTROL DID NOT FAIL: ' + requirement)
