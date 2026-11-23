"""Execute the preserved immutable oracle from the portable control bundle."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
output = HERE / "bundle-regression.json"
if output.exists():
    raise SystemExit("Existing bundle execution evidence is immutable")
manifest = json.loads((HERE / "control-subjects.manifest.json").read_text(encoding="utf-8"))
archive = HERE / "control-subjects.zip"
if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
    raise SystemExit("Control archive digest mismatch")
results = []
with tempfile.TemporaryDirectory(prefix="saipen-t1709-bundle-") as tmp:
    base = Path(tmp)
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if not (base / name).resolve().is_relative_to(base.resolve()):
                raise SystemExit("Unsafe control archive member")
            if hashlib.sha256(bundle.read(name)).hexdigest() != manifest["files"][name]:
                raise SystemExit("Control member digest mismatch")
        bundle.extractall(base)
    for stage, expected_exit in (("subject-red-lock", 1), ("subject-green-final", 0)):
        target = base / (stage + "-run")
        shutil.copytree(base / "base", target)
        shutil.copytree(base / stage, target, dirs_exist_ok=True)
        identity = json.loads((HERE / (stage.removeprefix("subject-") + ".json")).read_text())
        for rel, digest in {**identity["verifier_files"], **identity["subject_files"]}.items():
            if hashlib.sha256((target / rel).read_bytes()).hexdigest() != digest:
                raise SystemExit("Archived control identity changed: " + rel)
        run = subprocess.run([sys.executable, "-B", "tools/test_t1709_audit_starvation.py"],
                             cwd=target, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=120)
        results.append({"stage": stage, "exit_code": run.returncode,
                        "verifier": identity["verifier"], "subject": identity["subject"],
                        "stdout": run.stdout, "stderr": run.stderr})
        if run.returncode != expected_exit:
            raise SystemExit(run.stdout + run.stderr)
output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"pair": [{k: r[k] for k in ("stage", "exit_code", "verifier", "subject")}
                          for r in results], "evidence": str(output)}))
