"""Read-only comparison with the saved final verification input inventory."""

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit
from saipen_engine.test_runner import _ignore_copy

record = json.loads(Path(__file__).with_name("subject-before-full.json").read_text(encoding="utf-8"))
files = {}
for directory, dirs, names in os.walk(ROOT):
    here = Path(directory)
    ignored = _ignore_copy(directory, [*dirs, *names])
    if here == ROOT:
        ignored |= set(core_unit.FINGERPRINT_EXCLUDED)
    dirs[:] = sorted(name for name in dirs if name not in ignored)
    for name in names:
        path = here / name
        if name not in ignored and path.is_file():
            files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
changed = [name for name in sorted(files.keys() | record["files"].keys())
           if files.get(name) != record["files"].get(name)]
print(json.dumps({"unchanged": not changed, "changed_paths": changed,
                  "record_fingerprint": record["fingerprint"],
                  "current_fingerprint": core_unit.tree_fingerprint(ROOT)}, indent=2))
