"""Capture the bounded owned delta without staging or reverting other work."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PATHS = {
    "tools/saipen_engine/release.py": HERE / "before/release.py",
    "tools/test_t1746_crew_terminal_outcome.py": (
        HERE / "before/test_t1746_crew_terminal_outcome.py"
    ),
    "tools/test_t1750_release_boundary.py": None,
}
patches = []
manifest = {}
for name, before in PATHS.items():
    previous = before.read_bytes() if before else b""
    current = (ROOT / name).read_bytes()
    manifest[name] = {
        "before_sha256": hashlib.sha256(previous).hexdigest() if before else None,
        "after_sha256": hashlib.sha256(current).hexdigest(),
    }
    patches.extend(difflib.unified_diff(
        previous.decode("utf-8").splitlines(keepends=True),
        current.decode("utf-8").splitlines(keepends=True),
        fromfile="a/" + name if before else "/dev/null",
        tofile="b/" + name,
    ))
(HERE / "owned.patch").write_bytes("".join(patches).encode("utf-8"))
index = subprocess.run(
    ["git", "ls-files", "--stage", "-z"], cwd=ROOT, capture_output=True, check=True,
).stdout
saved_index = HERE / "index-entries.bin"
if not saved_index.exists():
    saved_index.write_bytes(index)
manifest["git_index_entries_sha256"] = hashlib.sha256(saved_index.read_bytes()).hexdigest()
manifest["git_index_entries_unchanged"] = index == saved_index.read_bytes()
(HERE / "ownership.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8",
)
print(json.dumps(manifest, indent=2))
