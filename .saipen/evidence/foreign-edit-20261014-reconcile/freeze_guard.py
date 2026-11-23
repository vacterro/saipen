"""Hold a tree under test at the bytes that were tested (incident tooling, T-1759).

    python freeze_guard.py snapshot <snapshot-dir>
    python freeze_guard.py enforce  <snapshot-dir> <evidence-dir>

Run from the project root. `snapshot` copies every fingerprinted file of the
live tree and records its digest. `enforce` compares the live tree with that
copy: a changed or deleted file is restored from the snapshot, and a file the
snapshot never held is moved out, each after its live bytes are saved under
<evidence-dir>/<UTC stamp>/. Prints one JSON object; `drift` is empty when the
tree already matched. The file set is the one `core_unit.tree_fingerprint`
digests, so a clean `enforce` means the family record of that snapshot cites.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "tools")

from saipen_engine.core_unit import FINGERPRINT_EXCLUDED, tree_fingerprint  # noqa: E402
from saipen_engine.test_runner import _ignore_copy  # noqa: E402

MANIFEST = "manifest.json"


def live_files(base: Path) -> dict:
    found = {}
    for directory, dirnames, filenames in os.walk(base):
        here = Path(directory)
        ignored = _ignore_copy(directory, [*dirnames, *filenames])
        if here == base:
            ignored |= set(FINGERPRINT_EXCLUDED)
        dirnames[:] = sorted(name for name in dirnames if name not in ignored)
        for name in filenames:
            path = here / name
            if name not in ignored and path.is_file():
                relative = path.relative_to(base).as_posix()
                found[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def snapshot(target: Path) -> dict:
    base = Path(".").resolve()
    files = live_files(base)
    for relative in files:
        destination = target / "files" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base / relative, destination)
    record = {"fingerprint": tree_fingerprint(base), "files": files}
    (target / MANIFEST).write_text(json.dumps(record, indent=0, sort_keys=True), encoding="utf-8")
    return {"files": len(files), "fingerprint": record["fingerprint"]}


def enforce(source: Path, evidence: Path) -> dict:
    base = Path(".").resolve()
    record = json.loads((source / MANIFEST).read_text(encoding="utf-8"))
    wanted = record["files"]
    live = live_files(base)
    drift = sorted(name for name in set(wanted) | set(live) if wanted.get(name) != live.get(name))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for relative in drift:
        path = base / relative
        if path.is_file():
            kept = evidence / stamp / relative
            kept.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, kept)
        if relative in wanted:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / "files" / relative, path)
        else:
            path.unlink()
    return {
        "drift": drift,
        "kept_under": str(evidence / stamp) if drift else None,
        "fingerprint_matches": tree_fingerprint(base) == record["fingerprint"],
        "fingerprint": record["fingerprint"][:16],
    }


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "snapshot":
        print(json.dumps(snapshot(Path(argv[1]).resolve())))
        return 0
    if len(argv) >= 3 and argv[0] == "enforce":
        result = enforce(Path(argv[1]).resolve(), Path(argv[2]).resolve())
        print(json.dumps(result))
        return 0 if result["fingerprint_matches"] else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
