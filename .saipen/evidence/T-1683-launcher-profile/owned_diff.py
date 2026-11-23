"""Bind the ticket's three-path delta against its exact inherited baseline."""

import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
paths = ["bootstrap/inject.sh", "bootstrap/inject.ps1", "tools/test_t1683_launcher_profile.py"]
receipt = {}
patch = []
for name in paths:
    previous = HERE / "pre" / name
    before = previous.read_bytes() if previous.is_file() else b""
    after = (ROOT / name).read_bytes()
    receipt[name] = {
        "before_sha256": hashlib.sha256(before).hexdigest(),
        "after_sha256": hashlib.sha256(after).hexdigest(),
    }
    patch.extend(difflib.unified_diff(
        before.decode("utf-8-sig").splitlines(keepends=True),
        after.decode("utf-8-sig").splitlines(keepends=True),
        fromfile="a/" + name, tofile="b/" + name,
    ))
(HERE / "owned.patch").write_text("".join(patch), encoding="utf-8")
(HERE / "scope.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"paths": paths, "patch_lines": len(patch)}))
