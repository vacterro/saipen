"""Append a read-only consumer revision; never overwrite prior evidence."""
import datetime
import hashlib
import json
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
consumer = root.parent.parent / "__SAITULS"
label = sys.argv[1]
if not label.startswith("snapshot-") or not label[9:].isdigit():
    raise ValueError("explicit snapshot-NNN label required")
destination = here / label
if destination.exists() or (here / (label + ".json")).exists():
    raise FileExistsError("immutable evidence revision already exists")
original = json.loads((here / "snapshot.json").read_text())
names = [row["path"] for row in original]
blobs = {name: (consumer / name).read_bytes() for name in names}
if any((consumer / name).read_bytes() != blob for name, blob in blobs.items()):
    raise RuntimeError("consumer changed during capture")
rows = []
for name, blob in blobs.items():
    target = destination / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)
    rows.append({"path": name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()})
result = {"observed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "files": rows}
(here / (label + ".json")).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
