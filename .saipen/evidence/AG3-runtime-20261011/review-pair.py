"""Independent REVIEW execution of the frozen pre-fix and current controls."""
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
prefix = sys.argv[1] if len(sys.argv) > 1 else "review"
red_stage, current_stage = prefix + "-red", prefix + "-current"
for stage in (red_stage, current_stage):
    if (HERE / (stage + ".json")).exists():
        raise SystemExit("Existing REVIEW evidence is immutable")
controls = HERE.parent / "T-1709-review"
manifest = json.loads((controls / "control-subjects.manifest.json").read_text(encoding="utf-8"))
archive = controls / "control-subjects.zip"
red = json.loads((HERE / "red-final.json").read_text(encoding="utf-8"))
if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
    raise SystemExit("Control archive digest changed")
temporary_root = Path(tempfile.gettempdir()).resolve()
with tempfile.TemporaryDirectory(prefix="saipen-t1712-review-", dir=temporary_root) as temporary:
    subject = Path(temporary).resolve()
    if not subject.is_relative_to(temporary_root):
        raise SystemExit("REVIEW temporary subject escaped")
    with zipfile.ZipFile(archive) as bundle:
        for prefix in ("base/", "subject-green-final/"):
            for name in bundle.namelist():
                if not name.startswith(prefix):
                    continue
                target = subject / name.removeprefix(prefix)
                if not target.resolve().is_relative_to(subject):
                    raise SystemExit("Unsafe archived path")
                data = bundle.read(name)
                if hashlib.sha256(data).hexdigest() != manifest["files"][name]:
                    raise SystemExit("Control archive member changed")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
    for relative, expected in {**red["subject_files"], **red["verifier_files"]}.items():
        original = HERE / "red-final-files" / relative
        if hashlib.sha256(original.read_bytes()).hexdigest() != expected:
            raise SystemExit("Preserved material changed: " + relative)
        shutil.copy2(original, subject / relative)
    subprocess.run([sys.executable, "-B", str(HERE / "control.py"), red_stage, str(subject)],
                   check=True)
subprocess.run([sys.executable, "-B", str(HERE / "control.py"), current_stage, str(ROOT)],
               check=True)
for stage, expected in ((red_stage, 1), (current_stage, 0)):
    record = json.loads((HERE / (stage + ".json")).read_text(encoding="utf-8"))
    if record["exit_code"] != expected or record["verifier"] != red["verifier"]:
        raise SystemExit("Independent REVIEW control mismatch")
