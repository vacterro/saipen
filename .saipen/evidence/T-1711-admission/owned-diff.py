"""Freeze attributable bytes and a readable exact patch without touching Git staging."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "owned-application.json"
if OUTPUT.exists():
    raise SystemExit("Existing owned-diff evidence is immutable")
owners = {}
for name in ("owned-before.json", "owned-before-extra.json", "owned-before-schema.json"):
    owners.update(json.loads((HERE / name).read_text(encoding="utf-8")))
rows = []
patch = []
for relative, before_hash in owners.items():
    after = (ROOT / relative).read_bytes()
    after_hash = hashlib.sha256(after).hexdigest()
    before = (HERE / "owned-before" / relative).read_bytes() if before_hash else b""
    if before_hash and hashlib.sha256(before).hexdigest() != before_hash:
        raise SystemExit("Pre-image changed: " + relative)
    if before == after:
        continue
    rows.append({"path": relative, "before_sha256": before_hash, "after_sha256": after_hash})
    patch.extend(difflib.unified_diff(before.decode("utf-8").replace("\r\n", "\n").splitlines(keepends=True),
                                    after.decode("utf-8").replace("\r\n", "\n").splitlines(keepends=True),
                                    fromfile="pre-T1711/" + relative, tofile="current/" + relative))
    copy = HERE / "owned-current" / relative
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(after)
OUTPUT.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
(HERE / "owned-changes.patch").write_text("".join(patch), encoding="utf-8")
print(json.dumps({"owned_changed_paths": len(rows), "paths": [row["path"] for row in rows]}))
