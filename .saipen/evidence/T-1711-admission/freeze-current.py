"""Keep each owned generation as a separate immutable attribution carrier."""
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
generation = sys.argv[1]
if not re.fullmatch(r"[a-z0-9-]{1,50}", generation):
    raise SystemExit("invalid generation")
output = HERE / ("owned-application-" + generation + ".json")
patch_path = HERE / ("owned-changes-" + generation + ".patch")
copies = HERE / ("owned-current-" + generation)
if output.exists() or patch_path.exists() or copies.exists():
    raise SystemExit("existing generation evidence is immutable")
owners = {}
for name in ("owned-before.json", "owned-before-extra.json", "owned-before-schema.json"):
    owners.update(json.loads((HERE / name).read_text(encoding="utf-8")))
rows, changes = [], []
for relative, expected in owners.items():
    target = (ROOT / relative).resolve()
    if not target.is_relative_to(ROOT.resolve()):
        raise SystemExit("owned path escaped")
    after = target.read_bytes()
    before = (HERE / "owned-before" / relative).read_bytes() if expected else b""
    if expected and hashlib.sha256(before).hexdigest() != expected:
        raise SystemExit("preserved pre-image changed: " + relative)
    if before == after:
        continue
    rows.append({"path": relative, "before_sha256": expected,
                 "after_sha256": hashlib.sha256(after).hexdigest()})
    changes.extend(difflib.unified_diff(
        before.decode("utf-8").replace("\r\n", "\n").splitlines(keepends=True),
        after.decode("utf-8").replace("\r\n", "\n").splitlines(keepends=True),
        fromfile="pre-T1711/" + relative, tofile=generation + "/" + relative))
    destination = copies / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(after)
if len(rows) != 13:
    raise SystemExit("owned scope differs from thirteen paths; investigate")
output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
patch_path.write_text("".join(changes), encoding="utf-8")
print(json.dumps({"generation": generation, "owned_paths": len(rows),
                  "record": str(output), "patch": str(patch_path)}))
