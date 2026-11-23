"""Execute a frozen permission oracle and preserve exact subject/verifier bytes."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
stage = sys.argv[1]
subject_root = Path(sys.argv[2]).resolve()
output = HERE / f"{stage}.json"
if output.exists():
    raise SystemExit("Control evidence already exists")
subject_paths = ["tools/saipen_engine/audit_manifest.py", "tools/saipen_engine/paths.py",
                 "tools/saipen_engine/host_bootstrap.py", "tools/saipen_engine/reconcile.py",
                 "tools/saipen.py", "tools/saipen_engine/init_project.py"]
oracle_paths = ["tools/test_t1712_manifest_runtime.py", "tools/test_control_primitives.py",
                "tools/test_fixture_support.py", "tools/test_hermetic_env.py"]
command = [sys.executable, "-B", "tools/test_t1712_manifest_runtime.py"]


def hashes(paths):
    return {rel: hashlib.sha256((subject_root / rel).read_bytes()).hexdigest() for rel in paths}


def identity(mapping, command_text=""):
    parts = [f"{rel}={sha}" for rel, sha in sorted(mapping.items())]
    return hashlib.sha256((command_text + "\n" + "\n".join(parts)).encode()).hexdigest()


subject = hashes(subject_paths)
oracle = hashes(oracle_paths)
run = subprocess.run(command, cwd=subject_root, capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=180)
if hashes(subject_paths) != subject or hashes(oracle_paths) != oracle:
    raise SystemExit("Subject or verifier changed during execution")
result = {"stage": stage, "root": str(subject_root), "command": command,
          "python": sys.version, "verifier_files": oracle, "subject_files": subject,
          "verifier": identity(oracle, "python -B tools/test_t1712_manifest_runtime.py"),
          "subject": identity(subject), "exit_code": run.returncode,
          "stdout": run.stdout, "stderr": run.stderr}
if stage.startswith("red"):
    destination = HERE / (stage + "-files")
    if destination.exists():
        raise SystemExit("Pre-fix snapshot already exists")
    for rel in [*subject_paths, *oracle_paths]:
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(subject_root / rel, target)
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: result[key] for key in ("stage", "verifier", "subject", "exit_code")}))
print("\n".join(run.stderr.splitlines()[-4:]))
