"""Preserve material control bytes without publishing whole Git clones."""
import hashlib
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
material = (
    "tools/saipen_engine/audit_inbox.py", "tools/saipen_engine/audit_route.py",
    "tools/saipen_engine/router.py", "tools/saipen.py",
    "tools/test_t1709_audit_starvation.py", "tools/test_audit_inbox.py",
    "tools/test_fixture_support.py", "saipen/SOURCES.md",
)
archive = HERE / "control-subjects.zip"
manifest_path = HERE / "control-subjects.manifest.json"
if archive.exists() or manifest_path.exists():
    raise SystemExit("Existing control bundle is immutable")
manifest = {"base": "subject-green-final", "files": {}}
with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
    base = HERE / "subject-green-final"
    selected = [p for p in base.iterdir() if p.is_file()]
    for directory in ("tools", "saipen", "bootstrap", "tests", "extensions", "assets"):
        if (base / directory).exists():
            selected.extend(p for p in (base / directory).rglob("*") if p.is_file())
    for path in sorted(selected):
        if path.is_symlink() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        name = "base/" + path.relative_to(base).as_posix()
        raw = path.read_bytes()
        bundle.writestr(name, raw)
        manifest["files"][name] = hashlib.sha256(raw).hexdigest()
    for snapshot in sorted(HERE.glob("subject-*")):
        if not snapshot.is_dir():
            continue
        for rel in material:
            raw = (snapshot / rel).read_bytes()
            name = snapshot.name + "/" + rel
            bundle.writestr(name, raw)
            manifest["files"][name] = hashlib.sha256(raw).hexdigest()
manifest["archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
manifest["reproduction"] = (
    "Extract base into a disposable directory; overlay a subject-<stage> directory; "
    "run python -B tools/test_t1709_audit_starvation.py. "
    "subject-red-lock must report one failure among fourteen; subject-green-final passes fourteen."
)
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": len(manifest["files"]), "bytes": archive.stat().st_size,
                  "sha256": manifest["archive_sha256"]}))
