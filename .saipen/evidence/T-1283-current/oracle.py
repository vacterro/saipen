"""Run the unchanged repository regression against original/current native code."""
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

version = sys.argv[1]
assert version in ("original", "current")
relative = "tools/saipen_engine/conformance_lineage.py"
original = HERE / "conformance_lineage.original.py"
if version == "original" and not original.exists():
    original.write_bytes(subprocess.check_output([
        "git", "show", "78447758b13c69f307c215878253825cb0bfd863^:" + relative], cwd=ROOT))
subject = original.read_bytes() if version == "original" else (ROOT / relative).read_bytes()
verifier = hashlib.sha256(Path(__file__).read_bytes()
    + (ROOT / "tools/test_t1283_lineage_legacy_ingest.py").read_bytes()
    + (ROOT / "tools/test_hermetic_env.py").read_bytes()
    + b"unittest test_t1283_lineage_legacy_ingest; timeout=180").hexdigest()
with tempfile.TemporaryDirectory(prefix="saipen-t1283-native-") as temporary:
    copied = Path(temporary) / "subject"
    copied.mkdir()
    for name in ("tools", "saipen", "extensions", "bootstrap", "tests", "bin"):
        shutil.copytree(ROOT / name, copied / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("README.md", "VERSION"):
        shutil.copyfile(ROOT / name, copied / name)
    (copied / relative).write_bytes(subject)
    run = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_t1283_lineage_legacy_ingest"],
        cwd=copied / "tools", env=hermetic_env(), capture_output=True,
        text=True, encoding="utf-8", timeout=180)
record = {"version": version, "verifier": verifier,
          "subject": hashlib.sha256(subject).hexdigest(),
          "original_origin": "78447758b13c69f307c215878253825cb0bfd863^:" + relative,
          "exit_code": run.returncode, "verdict": "PASS" if run.returncode == 0 else "FAIL",
          "stdout": run.stdout, "stderr": run.stderr}
(HERE / (version + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: record[key] for key in ("version", "verifier", "subject", "exit_code", "verdict")}))
