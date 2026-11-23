"""Add only the new test's intent entry; prove all other index entries intact."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
here = Path(__file__).resolve().parent
target = "tools/test_t1765_finding_subtypes.py"
paths = [target, "tools/saipen_engine/findings.py"]


def index():
    return subprocess.run(
        ["git", "ls-files", "--stage", "-z"], cwd=root, check=True, capture_output=True,
    ).stdout


before = index()
owned = b"\t" + target.encode()
assert not any(row.endswith(owned) for row in before.split(b"\0") if row)
hashes = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}
(here / "index-before.bin").write_bytes(before)
subprocess.run(["git", "add", "--intent-to-add", "--", target], cwd=root, check=True)
after = index()
foreign_after = b"\0".join(row for row in after.split(b"\0") if row and not row.endswith(owned)) + b"\0"
assert foreign_after == before, "Foreign index changed; preserve it and inspect, never reset it."
assert hashes == {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}
report = {
    "intent_only": target,
    "foreign_entries_unchanged": len([row for row in before.split(b"\0") if row]),
    "before_sha256": hashlib.sha256(before).hexdigest(),
    "after_sha256": hashlib.sha256(after).hexdigest(),
    "product_bytes_unchanged": True,
}
(here / "index-intent.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
