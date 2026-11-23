"""Report source differences; never copy changes back to the live project."""
import hashlib
import json
import os
import sys
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.test_runner import _ignore_copy

subject = Path(json.loads((evidence / "location.json").read_text())["subject"])

def files(base):
    found = {}
    for directory, dirs, names in os.walk(base):
        ignored = _ignore_copy(directory, dirs + names)
        if Path(directory) == base:
            ignored.update({".git", ".saipen"})
        dirs[:] = [name for name in dirs if name not in ignored]
        for name in names:
            if name not in ignored:
                path = Path(directory) / name
                found[path.relative_to(base).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found

live, copied = files(root), files(subject)
differences = [{"path": name, "live": live.get(name), "subject": copied.get(name)}
               for name in sorted(live.keys() | copied.keys()) if live.get(name) != copied.get(name)]
(evidence / "source-differences.json").write_text(json.dumps(differences, indent=2) + "\n")
print(json.dumps(differences, indent=2))
