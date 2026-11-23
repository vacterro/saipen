"""Refresh only this attempt's before/after evidence, never root subjects."""

import difflib
import hashlib
import json
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
paths = (
    "tools/saipen.py",
    "tools/test_t1631_argv_values.py",
    "tools/test_adaptive_runtime.py",
    "tools/test_intent_audit_fixes.py",
    "tools/test_t1327_zero_manual_recovery.py",
    "tools/test_t1557_mail_binding.py",
    "tools/test_t1363_zero_manual_entry.py",
)
scope = {}
diff = []
for path in paths:
    saved = evidence / "pre" / path
    if not saved.is_file() and path != "tools/test_t1631_argv_values.py":
        raise SystemExit("missing inherited bytes: " + path)
    before = saved.read_bytes() if saved.is_file() else b""
    after = (root / path).read_bytes()
    scope[path] = {
        "before_sha256": hashlib.sha256(before).hexdigest(),
        "after_sha256": hashlib.sha256(after).hexdigest(),
    }
    diff.extend(difflib.unified_diff(
        before.decode("utf-8").splitlines(keepends=True),
        after.decode("utf-8").splitlines(keepends=True),
        fromfile="a/" + path,
        tofile="b/" + path,
    ))
(evidence / "owned.patch").write_text("".join(diff), encoding="utf-8", newline="")
(evidence / "scope.json").write_text(json.dumps(scope, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"paths": list(scope), "count": len(scope)}))
