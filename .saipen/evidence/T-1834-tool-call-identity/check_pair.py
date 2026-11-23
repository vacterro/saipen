"""Keep the final oracle fixed while changing only its imported runner subject."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
oracle = ROOT / "tools/test_t1834_tool_call_identity.py"
code = '''
import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path('tools').resolve()))
import saipen_engine
name='saipen_engine.test_runner'
spec=importlib.util.spec_from_file_location(name,sys.argv[1])
subject=importlib.util.module_from_spec(spec)
sys.modules[name]=subject
spec.loader.exec_module(subject)
suite=unittest.defaultTestLoader.discover('tools',pattern='test_t1834_tool_call_identity.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
'''
rows = []
for name, subject in (("prefix", HERE / "prefix-test_runner.py"),
                      ("postfix", ROOT / "tools/saipen_engine/test_runner.py")):
    result = subprocess.run([sys.executable, "-B", "-c", code, str(subject)], cwd=ROOT,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=45)
    (HERE / f"{name}-final-oracle.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    rows.append({"name": name, "oracle_sha256": hashlib.sha256(oracle.read_bytes()).hexdigest(),
                 "subject_sha256": hashlib.sha256(subject.read_bytes()).hexdigest(),
                 "exit_code": result.returncode})
(HERE / "regression-pair.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
assert [row["exit_code"] for row in rows] == [1, 0], rows
print(json.dumps(rows))
