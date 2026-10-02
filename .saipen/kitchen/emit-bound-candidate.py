import difflib
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="strict")
root = Path(__file__).resolve().parents[2]
candidate = (root / sys.argv[1]).resolve()
assert candidate.is_relative_to(root / ".saipen/evidence")
data = json.loads((candidate / "manifest.json").read_text(encoding="utf-8"))
assert data["runs"]["before"]["failures"] > 0
assert data["runs"]["before"]["errors"] == 0
assert data["runs"]["candidate"]["ok"]
parts = ["*** Begin Patch"]
for kind in ("subject", "oracle"):
    rel = data[kind]
    target = (root / rel).resolve()
    assert target.is_relative_to(root)
    updated = (candidate / target.name).read_bytes()
    before_key = "before_sha256" if kind == "subject" else "oracle_before_sha256"
    after_key = "after_sha256" if kind == "subject" else "oracle_sha256"
    assert hashlib.sha256(updated).hexdigest() == data[after_key]
    if data[before_key] is None:
        assert not target.exists()
        parts.append("*** Add File: " + rel)
        parts.extend("+" + line for line in updated.decode("utf-8").splitlines())
        continue
    original = target.read_bytes()
    assert hashlib.sha256(original).hexdigest() == data[before_key]
    (candidate / (target.name + ".before")).write_bytes(original)
    diff = list(difflib.unified_diff(original.decode("utf-8").splitlines(),
                                   updated.decode("utf-8").splitlines(), n=3))
    assert diff
    parts.append("*** Update File: " + rel)
    parts.extend("@@" if line.startswith("@@") else line for line in diff[2:])
parts.append("*** End Patch")
print("\n".join(parts))
