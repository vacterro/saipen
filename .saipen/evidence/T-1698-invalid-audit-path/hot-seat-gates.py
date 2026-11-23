"""Current VERIFY/REVIEW evidence without replacing old attempts."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
prefix = sys.argv[1]
oracle = OUT / "regression.py"
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(oracle) == "8732220cbe13c4a8000201039e652c24fd462f8a67d142fc2410822969ed352d"
owners = [ROOT / "tools/saipen_engine/audit_inbox.py", ROOT / "tools/test_audit_inbox.py"]
outside = [ROOT / path for path in ("tools/saipen_engine/subs.py", "tools/validate.py", "tools/saipen.py", "tools/improve.py")]
before = {str(path.relative_to(ROOT)): sha(path) for path in owners + outside}
for path in owners:
    ast.parse(path.read_text(encoding="utf-8"))
records = []
for label, subject, expected in (("pre", OUT / "pre/audit_inbox.py", 1),
                                 ("post", owners[0], 0)):
    result = subprocess.run([sys.executable, "-B", str(oracle), str(subject)],
                            cwd=ROOT, capture_output=True, timeout=60)
    raw = result.stdout + result.stderr
    (OUT / (prefix + "-" + label + ".txt")).write_bytes(raw)
    assert result.returncode == expected and b"Ran 4 tests" in raw and b"ERROR:" not in raw, raw
    assert (b"FAILED (failures=2)" if expected else b"\nOK") in raw, raw
    records.append({"label": label, "exit_code": result.returncode,
                    "subject_sha256": sha(subject), "output_sha256": hashlib.sha256(raw).hexdigest()})

def definitions(path):
    return {node.name: ast.dump(node) for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))}

previous = definitions(OUT / "pre/test_audit_inbox.py")
current = definitions(owners[1])
assert all(current.get(name) == value for name, value in previous.items())
assert definitions(oracle)["InvalidPathTests"] == current["InvalidPathTests"]
after = {str(path.relative_to(ROOT)): sha(path) for path in owners + outside}
assert before == after
record = {"verifier_sha256": sha(oracle), "runs": records,
          "prior_test_definitions_identical": len(previous),
          "permanent_regression_ast_identical": True, "subject_hashes": after,
          "source_hashes_unchanged": before == after}
(OUT / (prefix + "-gates.json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
