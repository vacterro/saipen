"""Compare the copied family subject with current bytes under the same rules."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import FINGERPRINT_EXCLUDED
from saipen_engine.test_runner import _ignore_copy


def manifest(root):
    files = {}
    for directory, directories, filenames in os.walk(root):
        here = Path(directory)
        ignored = _ignore_copy(directory, [*directories, *filenames])
        if here == root:
            ignored |= set(FINGERPRINT_EXCLUDED)
        directories[:] = sorted(name for name in directories if name not in ignored)
        for name in filenames:
            path = here / name
            if name not in ignored and path.is_file():
                files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


copied = manifest(Path(sys.argv[1]).resolve())
live = manifest(ROOT)
print(json.dumps({name: {"copied": copied.get(name), "live": live.get(name)}
                  for name in sorted(copied.keys() | live.keys()) if copied.get(name) != live.get(name)}, indent=2))
