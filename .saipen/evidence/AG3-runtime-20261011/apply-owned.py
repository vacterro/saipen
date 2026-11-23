"""Apply only the claimed, reviewed runtime slice over its exact baseline."""
import difflib
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCRATCH = Path("V:/_TEMP_/saipen-t1712-runtime-20261011")
red = json.loads((HERE / "red-final.json").read_text(encoding="utf-8"))
green = json.loads((HERE / "green-final.json").read_text(encoding="utf-8"))
state = (ROOT / ".saipen/STATE.md").read_text(encoding="utf-8")
if "phase: BUILD\n" not in state or "task: T-1712\n" not in state or "agent: saipen-cli\n" not in state:
    raise SystemExit("T-1712 does not own BUILD")
output = HERE / "owned-application.json"
if output.exists():
    raise SystemExit("Owned patch already applied")
for rel, sha in red["subject_files"].items():
    if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != sha:
        raise SystemExit("Production baseline changed: " + rel)
for rel, sha in green["subject_files"].items():
    if hashlib.sha256((SCRATCH / rel).read_bytes()).hexdigest() != sha:
        raise SystemExit("Corrected subject changed: " + rel)
neighbor = "tools/test_t1647_machine_runtime.py"
with zipfile.ZipFile(HERE.parent / "T-1709-review/control-subjects.zip") as bundle:
    if (ROOT / neighbor).read_bytes() != bundle.read("base/" + neighbor):
        raise SystemExit("Neighbor baseline changed")
new_test = "tools/test_t1712_manifest_runtime.py"
if (ROOT / new_test).exists():
    raise SystemExit("New oracle path already occupied")
records, patch = [], []
for rel in [*green["subject_files"], neighbor, new_test]:
    source, target = SCRATCH / rel, ROOT / rel
    before = target.read_bytes() if target.exists() else b""
    if before:
        backup = HERE / "production-before" / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
    after = source.read_bytes()
    patch.extend(difflib.unified_diff(before.decode("utf-8").splitlines(True),
                                    after.decode("utf-8").splitlines(True),
                                    fromfile="a/" + rel, tofile="b/" + rel))
    target.write_bytes(after)
    records.append({"path": rel, "before_sha256": hashlib.sha256(before).hexdigest(),
                    "after_sha256": hashlib.sha256(after).hexdigest()})
(HERE / "owned-changes.patch").write_text("".join(patch), encoding="utf-8")
output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"owned_work": "T-1712", "changed_paths": [r["path"] for r in records]}))
