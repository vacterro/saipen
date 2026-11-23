"""Check the exact final current-06 verification inventory without writes."""

import hashlib
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine import core_unit
from saipen_engine.test_runner import _ignore_copy

record = json.loads(Path(__file__).with_name("subject-before-full-current-06.json").read_text("utf-8"))
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
changed = [name for name in sorted(files.keys() | record["files"].keys())
           if files.get(name) != record["files"].get(name)]
print(json.dumps({"unchanged": not changed, "changed_paths": changed,
                  "record_fingerprint": record["fingerprint"],
                  "current_fingerprint": core_unit.tree_fingerprint(root)}))
raise SystemExit(1 if changed else 0)
