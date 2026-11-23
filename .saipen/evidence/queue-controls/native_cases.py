"""Read-only original/current subject comparisons for already implemented Work."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from test_hermetic_env import hermetic_env

kind, version = sys.argv[1:]
assert kind in ("posix", "lag") and version in ("original", "current")
subject_rel = ("tools/saipen_engine/entry_resolver.py" if kind == "posix"
               else "tools/test_t1505_core_unit_sandbox_reclaim.py")
if kind == "lag" and version == "original":
    original = HERE / "held-original.py"
    if not original.exists():
        original.write_bytes(subprocess.check_output([
            "git", "show", "fb91135ab9b59520485edcd3a0c73bb395cc663a:" + subject_rel], cwd=ROOT))
if kind == "posix" and version == "original":
    original = HERE / "entry-original.py"
    if not original.exists():
        original.write_bytes(subprocess.check_output([
            "git", "show", "423dfed4^:" + subject_rel], cwd=ROOT))
    mistaken = HERE / "posix-original.json"
    preserved = HERE / "posix-identical-subject-diagnostic.json"
    if mistaken.exists() and not preserved.exists():
        mistaken.rename(preserved)
if version == "current":
    data = (ROOT / subject_rel).read_bytes()
else:
    source = (HERE / "entry-original.py"
              if kind == "posix" else HERE / "held-original.py")
    data = source.read_bytes()
subject_hash = hashlib.sha256(data).hexdigest()
verifier_hash = hashlib.sha256(Path(__file__).read_bytes()
    + ((ROOT / "tools/test_t1515_posix_shell_entry.py").read_bytes() if kind == "posix"
       else (HERE / "held_lag.py").read_bytes())).hexdigest()
with tempfile.TemporaryDirectory(prefix="saipen-queue-native-") as temp:
    copied = Path(temp) / "subject"
    copied.mkdir()
    for name in ("tools", "saipen", "extensions", "bootstrap", "tests", "bin"):
        shutil.copytree(ROOT / name, copied / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("README.md", "VERSION"):
        shutil.copyfile(ROOT / name, copied / name)
    (copied / subject_rel).write_bytes(data)
    if kind == "posix":
        command = [sys.executable, "-B", "-m", "unittest", "test_t1515_posix_shell_entry"]
        cwd = copied / "tools"
    else:
        command = [sys.executable, "-B", str(HERE / "held_lag.py")]
        cwd = copied
    run = subprocess.run(command, cwd=cwd, env=hermetic_env(), capture_output=True,
                         text=True, encoding="utf-8", timeout=180)
record = {"kind": kind, "version": version, "subject": subject_hash,
          "verifier": verifier_hash, "exit_code": run.returncode,
          "verdict": "PASS" if run.returncode == 0 else "FAIL",
          "stdout": run.stdout, "stderr": run.stderr}
(HERE / (kind + "-" + version + ".json")).write_text(
    json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: record[key] for key in (
    "kind", "version", "subject", "verifier", "exit_code", "verdict")}))
