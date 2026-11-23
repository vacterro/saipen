"""Keep a hash-only inventory so later drift has exact path attribution."""

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit
from saipen_engine.test_runner import _ignore_copy

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
target = Path(__file__).with_name("subject-before-full.json")
assert not target.exists(), "preserve the earlier inventory rather than overwriting it"
fingerprint = core_unit.tree_fingerprint(ROOT)
target.write_text(json.dumps({"fingerprint": fingerprint, "files": files}, indent=2) + "\n",
                  encoding="utf-8")
print(json.dumps({"record": str(target), "fingerprint": fingerprint, "paths": len(files)}))
