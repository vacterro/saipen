import difflib
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="strict")
root = Path(__file__).resolve().parents[2]
out = root / ".saipen/evidence/T-1586-scenario-candidate"
data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
assert data["runs"]["before"]["failures"] == 4
assert data["runs"]["before"]["errors"] == 0
assert data["runs"]["candidate"]["ok"]
parts = ["*** Begin Patch"]
for record in data["subjects"]:
    target = root / record["path"]
    original, updated = target.read_bytes(), (out / target.name).read_bytes()
    assert hashlib.sha256(original).hexdigest() == record["before_sha256"]
    assert hashlib.sha256(updated).hexdigest() == record["after_sha256"]
    diff = list(difflib.unified_diff(original.decode("utf-8").splitlines(),
                                   updated.decode("utf-8").splitlines(), n=3))
    assert diff
    parts.append("*** Update File: " + record["path"])
    parts.extend("@@" if line.startswith("@@") else line for line in diff[2:])
oracle = data["oracle"]
target = root / oracle["path"]
assert not target.exists()
updated = (out / target.name).read_bytes()
assert hashlib.sha256(updated).hexdigest() == oracle["sha256"]
parts.append("*** Add File: " + oracle["path"])
parts.extend("+" + line for line in updated.decode("utf-8").splitlines())
parts.append("*** End Patch")
print("\n".join(parts))
