import importlib.util
import json
import sys
import unittest
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
draft = Path(json.loads((evidence / 'scratch.json').read_text())['project'])
sys.path.insert(0, str(root / 'tools'))
sys.path.append(str(draft / 'tools'))
spec = importlib.util.spec_from_file_location('independent_t1631_oracle',
                                             draft / 'tools/test_t1631_option_values.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.TOOLS = root / 'tools'
module.ROOT = root
with (evidence / 'live-candidate-review.out.txt').open('w', encoding='utf-8') as stream:
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(module))
payload = {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
           'failed_ids': [test.id() for test, _ in result.failures + result.errors],
           'subject': 'live CLI candidate; no source mutation',
           'oracle': str(draft / 'tools/test_t1631_option_values.py')}
(evidence / 'live-candidate-review.json').write_text(json.dumps(payload, indent=2) + '\n',
                                                   encoding='utf-8')
print(json.dumps(payload))
raise SystemExit(not result.wasSuccessful())
