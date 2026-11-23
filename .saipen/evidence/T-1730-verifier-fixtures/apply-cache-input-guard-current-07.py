"""Apply exactly the two preimage-checked files of the owned fixture repair."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

directory = Path(__file__).resolve().parent
root = directory.parents[2]
sys.path.insert(0, str(root / "tools"))
from saipen_engine import core_unit
from saipen_engine.paths import safe_atomic_write_bytes
from saipen_engine.state import parse_state
from saipen_engine.test_runner import _ignore_copy

record_path = directory / "apply-cache-input-guard-current-07.json"
if record_path.exists():
    raise SystemExit("Existing application evidence preserved.")
state = parse_state((root / ".saipen/STATE.md").read_text("utf-8"))
if (state.get("phase"), state.get("task")) != ("BUILD", "T-1730"):
    raise SystemExit("The owned BUILD T-1730 boundary is required.")
names = ("audit_checks.py", "test_t1581_phase_rename_knowledge.py")
changes = {}
for name in names:
    before = (directory / "before-cache-input-guard/tools" / name).read_bytes()
    if (root / "tools" / name).read_bytes() != before:
        raise SystemExit(f"Foreign preimage change refused: {name}")
    after = (directory / "cache-candidate/tools" / name).read_bytes()
    changes["tools/" + name] = {"before": hashlib.sha256(before).hexdigest(),
                               "after": hashlib.sha256(after).hexdigest()}


def staged():
    result = subprocess.run(["git", "--no-optional-locks", "diff", "--cached", "--binary"],
                            cwd=root, capture_output=True, check=True)
    return hashlib.sha256(result.stdout).hexdigest()


index_before = staged()
for name in names:
    safe_atomic_write_bytes(root / "tools" / name,
                            (directory / "cache-candidate/tools" / name).read_bytes(),
                            kind="owned T-1730 fixture repair", ownership_root=root)
index_after = staged()
files = {}
for current, directories, names in os.walk(root):
    here = Path(current)
    ignored = _ignore_copy(current, [*directories, *names])
    if here == root:
        ignored |= set(core_unit.FINGERPRINT_EXCLUDED)
    directories[:] = sorted(name for name in directories if name not in ignored)
    for name in names:
        path = here / name
        if name not in ignored and path.is_file():
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
previous = json.loads((directory / "subject-before-full-current-06.json").read_text("utf-8"))
changed = [name for name in sorted(files.keys() | previous["files"].keys())
           if files.get(name) != previous["files"].get(name)]
record = {"changes": changes, "staged_before": index_before, "staged_after": index_after,
          "staging_preserved": index_before == index_after, "changed_paths": changed,
          "fingerprint": core_unit.tree_fingerprint(root), "files": files}
record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
(directory / "subject-before-full-current-07.json").write_text(
    json.dumps({"fingerprint": record["fingerprint"], "files": files}, indent=2) + "\n",
    encoding="utf-8")
print(json.dumps({key: value for key, value in record.items() if key != "files"}, indent=2))
if not record["staging_preserved"] or changed != sorted(changes):
    raise SystemExit("Unexpected concurrent change preserved; inspect before continuing.")
