"""Fixed missing-inventory oracle, two actual reporter subjects."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
oracle = ROOT / "tools/test_t1835_verification_economics.py"
code = '''
import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path('tools').resolve()))
spec=importlib.util.spec_from_file_location('verification_metrics',sys.argv[1])
subject=importlib.util.module_from_spec(spec)
sys.modules['verification_metrics']=subject
spec.loader.exec_module(subject)
loader=unittest.TestLoader()
loader.testNamePatterns=['*incomplete_failure*']
suite=loader.discover('tools',pattern='test_t1835_verification_economics.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
'''
rows = []
for name, subject in (("prefix", HERE / "prefix-red-inventory.py"),
                      ("postfix", ROOT / "tools/verification_metrics.py")):
    result = subprocess.run([sys.executable, "-B", "-c", code, str(subject)], cwd=ROOT,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=15)
    (HERE / f"{name}-same-oracle.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    rows.append({"name": name, "exit_code": result.returncode,
                 "oracle_sha256": hashlib.sha256(oracle.read_bytes()).hexdigest(),
                 "subject_sha256": hashlib.sha256(subject.read_bytes()).hexdigest()})
(HERE / "red-inventory-pair.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
assert [row["exit_code"] for row in rows] == [1, 0], rows
print(json.dumps(rows))
