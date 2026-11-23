"""Apply exactly the parent-owned, preimage-checked membership correction."""

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

target = directory / "apply-membership-current-08.json"
if target.exists():
    raise SystemExit("Existing application evidence preserved.")
state = parse_state((root / ".saipen/STATE.md").read_text("utf-8"))
if (state.get("phase"), state.get("task")) != ("BUILD", "T-1726"):
    raise SystemExit("The parent-owned BUILD boundary is required.")
paths = ("tools/saipen_engine/closed_contracts.py", "tools/saipen_engine/regression_execution.py",
         "tools/test_t1726_closed_contracts.py")
changes = {}
for relative in paths:
    before = (directory / "before-membership-current-08" / relative).read_bytes()
    after = (directory / "candidate-membership-current-08" / relative).read_bytes()
    if (root / relative).read_bytes() != before:
        raise SystemExit("Foreign preimage refused: " + relative)
    changes[relative] = {"before": hashlib.sha256(before).hexdigest(),
                         "after": hashlib.sha256(after).hexdigest()}


def staged():
    value = subprocess.run(["git", "--no-optional-locks", "diff", "--cached", "--binary"],
                           cwd=root, capture_output=True, check=True).stdout
    return hashlib.sha256(value).hexdigest()


old_index = staged()
for relative in paths:
    safe_atomic_write_bytes(root / relative,
                            (directory / "candidate-membership-current-08" / relative).read_bytes(),
                            kind="owned T-1726 membership correction", ownership_root=root)
new_index = staged()
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
previous = json.loads((root / ".saipen/evidence/T-1730-verifier-fixtures/subject-before-full-current-07.json").read_text("utf-8"))
changed = [name for name in sorted(files.keys() | previous["files"].keys())
           if files.get(name) != previous["files"].get(name)]
result = {"changes": changes, "staged_before": old_index, "staged_after": new_index,
          "staging_preserved": old_index == new_index, "changed_paths": changed,
          "fingerprint": core_unit.tree_fingerprint(root), "files": files}
target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
(directory / "subject-before-full-membership-08.json").write_text(
    json.dumps({"fingerprint": result["fingerprint"], "files": files}, indent=2) + "\n",
    encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "files"}, indent=2))
if old_index != new_index or changed != sorted(paths):
    raise SystemExit("Unexpected concurrent change preserved; inspect it before further work.")
