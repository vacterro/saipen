"""Apply attributed T-1301 removals, retaining the exact recorded oracle."""
import ast
import difflib
import hashlib
from pathlib import Path

root = Path.cwd()
out = root / '.saipen/kitchen/t1298-recovery'
live = root / 'tools/validate.py'
before = live.read_bytes()
assert before == (out / 'worktree/tools/validate.py').read_bytes()
oracle = (root / '.saipen/kitchen/t1302-preserved/t1298-pure__tools__validate.py').read_bytes()
assert hashlib.sha256(oracle).hexdigest() == 'd8f8fd4ae5bcd67bdd6eadf202b1fbd607b99972a57c945e7c4b74154d184e99'
a, b = before.splitlines(keepends=True), oracle.splitlines(keepends=True)
pieces = []
for tag, i, j, k, l in difflib.SequenceMatcher(None, a, b).get_opcodes():
    if tag != 'equal':
        assert any(term in b''.join(a[i:j]) for term in [b'findings_json', b'FINDINGS_JSON_OUT', b'_record_structured', b'_emit_findings_json']), (tag, i, j)
    pieces.extend(a[i:j] if tag == 'equal' else b[k:l])
candidate = b''.join(pieces)
assert candidate == oracle
(out / 'validate.recorded-oracle.py').write_bytes(candidate)
# The exact oracle retains one foreign call. Its isolated warn() raises
# NameError (E-5946); remove that final T-1301 hook for a runnable candidate.
foreign = b'    _record_structured("warnings", msg, category=category)\r\n'
assert candidate.count(foreign) == 1
candidate = candidate.replace(foreign, b'')
assert b'_record_structured' not in candidate
tree = ast.parse(candidate)
warn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'warn')
namespace = {'warnings': {}}
exec(compile(ast.Module(body=[warn], type_ignores=[]), 'validate.py', 'exec'), namespace)
namespace['warn']('probe', 'isolation')
assert namespace['warnings'] == {'probe': ['isolation']}
(out / 'validate-isolation.diff').write_text(''.join(difflib.unified_diff(before.decode().splitlines(True), candidate.decode().splitlines(True), fromfile='foreign/tools/validate.py', tofile='isolated/tools/validate.py')), encoding='utf-8')
live.write_bytes(candidate)
print('Recorded oracle reconstructed exactly; final foreign-hook correction:', hashlib.sha256(candidate).hexdigest())
