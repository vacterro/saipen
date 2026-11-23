"""Verify that intent-to-add touched only the validator's two named paths."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OWN = {b"tools/test_t1750_release_boundary.py", b"tools/test_t1753_activation_launcher.py"}
before = (HERE / "index-entries.bin").read_bytes()
after = subprocess.run(
    ["git", "ls-files", "--stage", "-z"], cwd=ROOT, capture_output=True, check=True,
).stdout


def foreign(raw):
    return b"\0".join(entry for entry in raw.split(b"\0")
                      if entry and entry.split(b"\t", 1)[1] not in OWN)


result = {
    "before_sha256": hashlib.sha256(before).hexdigest(),
    "after_sha256": hashlib.sha256(after).hexdigest(),
    "foreign_entries_unchanged": foreign(before) == foreign(after),
    "named_paths": sorted(path.decode() for path in OWN),
    "named_entries": [entry.decode() for entry in after.split(b"\0")
                      if entry and entry.split(b"\t", 1)[1] in OWN],
}
(HERE / "index-intent.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
assert result["foreign_entries_unchanged"], "Unexpected foreign index change; preserve and inspect"
