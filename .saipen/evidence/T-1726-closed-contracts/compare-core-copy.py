"""Compare only the core family's declared content surface; no mutations."""

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit
from saipen_engine.test_runner import _ignore_copy

def manifest(base):
    result = {}
    for directory, dirnames, filenames in os.walk(base):
        here = Path(directory)
        ignored = _ignore_copy(directory, [*dirnames, *filenames])
        if here == base:
            ignored |= set(core_unit.FINGERPRINT_EXCLUDED)
        dirnames[:] = sorted(name for name in dirnames if name not in ignored)
        for name in filenames:
            path = here / name
            if name not in ignored and path.is_file():
                result[path.relative_to(base).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result

other = Path(sys.argv[1]).resolve()
assert other.is_dir()
left, right = manifest(ROOT), manifest(other)
differences = [{"path": path, "current": left.get(path), "copy": right.get(path)}
               for path in sorted(left.keys() | right.keys()) if left.get(path) != right.get(path)]
body = {"copy": str(other), "current_fingerprint": core_unit.tree_fingerprint(ROOT),
        "copy_fingerprint": core_unit.tree_fingerprint(other), "differences": differences}
target = Path(__file__).with_name("core-copy-comparison.json")
target.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
print(json.dumps(body, indent=2))
