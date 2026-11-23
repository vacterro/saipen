"""Fixed oracle, pre-guard publication predicate versus corrected predicate.

Adjacent impact infrastructure is held current. The prefix preserves the
observed pre-fix publication body by removing only its new scope check; it is
not represented as a historic checkout or production execution receipt.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
subject = ROOT / "tools/saipen_engine/focused_unit.py"
source = subject.read_text(encoding="utf-8")
guard = "        if issue := core_unit.full_scope_problem(record):\n            return issue\n"
assert source.count(guard) == 1
prefix = HERE / "pre-guard-publication.py"
prefix.write_text(source.replace(guard, "", 1), encoding="utf-8")
oracle = ROOT / "tools/test_t1836_verification_impact.py"
code = '''
import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path('tools').resolve()))
import saipen_engine
import saipen_engine.core_unit
name='saipen_engine.focused_unit'
spec=importlib.util.spec_from_file_location(name,sys.argv[1])
subject=importlib.util.module_from_spec(spec)
sys.modules[name]=subject
spec.loader.exec_module(subject)
saipen_engine.focused_unit=subject
loader=unittest.TestLoader()
loader.testNamePatterns=['*relabelled*']
suite=loader.discover('tools',pattern='test_t1836_verification_impact.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
'''
rows = []
for name, path in (("pre_guard_predicate", prefix), ("corrected", subject)):
    result = subprocess.run([sys.executable, "-B", "-c", code, str(path)], cwd=ROOT,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=30)
    (HERE / f"{name}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    rows.append({"name": name, "exit_code": result.returncode,
                 "oracle_sha256": hashlib.sha256(oracle.read_bytes()).hexdigest(),
                 "subject_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
(HERE / "scope-pair.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
assert [row["exit_code"] for row in rows] == [1, 0], rows
print(json.dumps(rows))
