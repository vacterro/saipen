"""Prepare an isolated draft, without editing the core-unit frozen subject."""
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
controls = ROOT / ".saipen/evidence/T-1709-review"
archive = controls / "control-subjects.zip"
manifest = json.loads((controls / "control-subjects.manifest.json").read_text(encoding="utf-8"))
if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
    raise SystemExit("Bad preserved control archive")
scratch = Path(tempfile.gettempdir()) / "saipen-t1712-runtime-20261011"
if scratch.exists():
    raise SystemExit("Scratch already exists; do not overwrite another draft")
scratch.mkdir()
with zipfile.ZipFile(archive) as bundle:
    for prefix in ("base/", "subject-green-final/"):
        for name in bundle.namelist():
            if not name.startswith(prefix):
                continue
            relative = name.removeprefix(prefix)
            target = scratch / relative
            if not target.resolve().is_relative_to(scratch.resolve()):
                raise SystemExit("Unsafe archive member")
            data = bundle.read(name)
            if hashlib.sha256(data).hexdigest() != manifest["files"][name]:
                raise SystemExit("Bad member digest")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
for rel in ("tools/saipen_engine/audit_manifest.py", "tools/saipen_engine/paths.py",
            "tools/saipen_engine/reconcile.py", "tools/saipen.py"):
    if (scratch / rel).read_bytes() != (ROOT / rel).read_bytes():
        raise SystemExit("Scratch is not the current subject: " + rel)
record = {"work": "T-1712", "status": "draft only; no production application or claim",
          "scratch": str(scratch), "archive_sha256": manifest["archive_sha256"],
          "production_files_changed": 0}
(HERE / "scratch.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
