"""Bind the same portable-field/transport oracle to its actual subjects."""

import hashlib
import json
import re
import subprocess
import shutil
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
label = sys.argv[1]
assert re.fullmatch("[a-z0-9-]+", label)
command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tools",
           "-p", "test_portable_floor_fields.py", "-v"]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
verifier = {"command": command, "files": {
    name: sha(ROOT / name) for name in ("tools/test_portable_floor_fields.py", "tools/audit_floor.py",
                                       "tools/saipen_engine/board.py", "saipen/REGISTRY.json")}}
TESTED = ROOT
if label.startswith("red-final"):
    TESTED = EVIDENCE / "original-subject"
    if not TESTED.exists():
        shutil.copytree(ROOT, TESTED, ignore=lambda directory, names: [
            name for name in names if name in {".git", "__pycache__", ".ruff_cache", ".pytest_cache"}
            or (Path(directory) == ROOT and name == ".saipen")
        ])
        for name in ("tests/validate.sh", "tests/validate.ps1", "tools/audit_parity.py"):
            original = subprocess.run(["git", "show", "HEAD:" + name], cwd=ROOT,
                                      capture_output=True, check=True).stdout
            (TESTED / name).write_bytes(original)
    assert all(sha(TESTED / name) == value for name, value in verifier["files"].items())
subject = {name: sha(TESTED / name) for name in (
    "tests/validate.sh", "tests/validate.ps1", "tools/audit_parity.py",
)}
digest = lambda data: hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
result = subprocess.run(command, cwd=TESTED, capture_output=True, text=True,
                        encoding="utf-8", timeout=180)
output = result.stdout + result.stderr
record = {"exit_code": result.returncode, "verifier": digest(verifier), "subject": digest(subject),
          "verifier_identity": verifier, "subject_identity": subject,
          "output_sha256": hashlib.sha256(output.encode()).hexdigest()}
(EVIDENCE / f"{label}.txt").write_text(output, encoding="utf-8")
(EVIDENCE / f"{label}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(output[-1300:])
print(json.dumps({key: record[key] for key in ("exit_code", "verifier", "subject")}))
sys.exit(result.returncode)
