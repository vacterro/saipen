"""Reconstruct the immutable pre-fix control and execute the current pair."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
controls = HERE.parent / "T-1709-review"
manifest = json.loads((controls / "control-subjects.manifest.json").read_text(encoding="utf-8"))
archive = controls / "control-subjects.zip"
red = json.loads((HERE / "red-final.json").read_text(encoding="utf-8"))
if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
    raise SystemExit("Control archive digest changed")
temporary_root = Path("C:/Users/vac34/AppData/Local/Temp").resolve()
with tempfile.TemporaryDirectory(prefix="saipen-t1712-verify-", dir=temporary_root) as temporary:
    subject = Path(temporary).resolve()
    if not subject.is_relative_to(temporary_root):
        raise SystemExit("Control cleanup boundary escaped")
    with zipfile.ZipFile(archive) as bundle:
        for prefix in ("base/", "subject-green-final/"):
            for name in bundle.namelist():
                if not name.startswith(prefix):
                    continue
                target = subject / name.removeprefix(prefix)
                if not target.resolve().is_relative_to(subject):
                    raise SystemExit("Unsafe archived control path")
                data = bundle.read(name)
                if hashlib.sha256(data).hexdigest() != manifest["files"][name]:
                    raise SystemExit("Control member changed")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
    for rel, sha in {**red["subject_files"], **red["verifier_files"]}.items():
        source = HERE / "red-final-files" / rel
        if hashlib.sha256(source.read_bytes()).hexdigest() != sha:
            raise SystemExit("Frozen material bytes changed: " + rel)
        shutil.copy2(source, subject / rel)
    subprocess.run([sys.executable, "-B", str(HERE / "control.py"), "verify-red", str(subject)],
                   check=True)
subprocess.run([sys.executable, "-B", str(HERE / "control.py"), "verify-green", str(ROOT)],
               check=True)
for stage, expected in (("verify-red", 1), ("verify-green", 0)):
    record = json.loads((HERE / (stage + ".json")).read_text(encoding="utf-8"))
    if record["exit_code"] != expected or record["verifier"] != red["verifier"]:
        raise SystemExit("Current-cycle frozen control mismatch")
