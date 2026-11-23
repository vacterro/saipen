"""Independent current-tree review; retain both actual verifier exits."""
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
oracle = OUT / "regression.py"
assert sha(oracle) == "8732220cbe13c4a8000201039e652c24fd462f8a67d142fc2410822969ed352d"
records = []
for label, subject, expected in (
    ("pre", OUT / "pre/audit_inbox.py", 1),
    ("post", ROOT / "tools/saipen_engine/audit_inbox.py", 0),
):
    result = subprocess.run([sys.executable, "-B", str(oracle), str(subject)],
                            cwd=ROOT, env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                            capture_output=True, timeout=60)
    output = OUT / f"review-{label}.txt"
    output.write_bytes(result.stdout + result.stderr)
    records.append({"subject": str(subject), "subject_sha256": sha(subject),
                    "exit_code": result.returncode, "output": output.name})
    assert result.returncode == expected, records[-1]
    assert b"Ran 4 tests" in output.read_bytes()
    assert b"ERROR:" not in output.read_bytes()
    if expected:
        assert b"FAILED (failures=2)" in output.read_bytes()

def definitions(path):
    return {node.name: ast.dump(node) for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))}

old_tests = definitions(OUT / "pre/test_audit_inbox.py")
current_tests = definitions(ROOT / "tools/test_audit_inbox.py")
assert all(current_tests.get(name) == value for name, value in old_tests.items())
assert definitions(oracle)["InvalidPathTests"] == current_tests["InvalidPathTests"]
previous = json.loads((OUT.parent / "T-1697-audit-drop-queue/final-owned-hashes.json").read_text())
owned = {"tools/saipen_engine/audit_inbox.py", "tools/test_audit_inbox.py"}
for path, digest in previous["owned_current_sha256"].items():
    if path not in owned:
        assert sha(ROOT / path) == digest, path
assert sha(ROOT / "tools/validate.py") == previous["outside_owner_validate_sha256"]
staged = subprocess.run(["git", "-c", "core.safecrlf=false", "diff", "--cached", "--binary"],
                        cwd=ROOT, capture_output=True, timeout=30)
assert staged.returncode == 0
old_staged = (OUT.parent / "T-1697-audit-drop-queue/current-index.patch").read_bytes()
assert staged.stdout.replace(b"\r\n", b"\n") == old_staged.replace(b"\r\n", b"\n")
baseline = json.loads((OUT.parent / "T-1696-queued-audapack/baseline.json").read_text())
rows = {}
for line in (ROOT / ".saipen/BOARD.md").read_bytes().splitlines(keepends=True):
    match = re.match(rb"- \[[ /x]\] (T-\d+) ", line)
    if match:
        rows[match[1].decode()] = hashlib.sha256(line).hexdigest()
assert all(rows.get(ticket) == digest for ticket, digest in baseline["preexisting_blocked_records"].items())
patch = []
for path, old in (("tools/saipen_engine/audit_inbox.py", "audit_inbox.py"),
                  ("tools/test_audit_inbox.py", "test_audit_inbox.py")):
    patch.extend(difflib.unified_diff((OUT / "pre" / old).read_text().splitlines(True),
                                    (ROOT / path).read_text().splitlines(True),
                                    fromfile="pre/" + path, tofile="post/" + path))
(OUT / "owned.patch").write_text("".join(patch), encoding="utf-8")
record = {"verifier_sha256": sha(oracle), "runs": records,
          "prior_test_definitions_identical": len(old_tests),
          "permanent_oracle_ast_identical": True,
          "prior_parked_rows_byte_identical": len(baseline["preexisting_blocked_records"]),
          "other_feature_paths_unchanged": 7, "unowned_validate_unchanged": True,
          "staged_diff_unchanged_after_capture_eol_normalization": True,
          "memory_promotion": "NO: small diagnostic path fix, no new durable non-cheap lesson"}
(OUT / "review.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
