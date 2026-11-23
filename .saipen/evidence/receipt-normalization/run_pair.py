"""Measure one fixed restoration oracle against current production bytes."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).resolve().parent
label = sys.argv[1]
assert re.fullmatch(r"[a-z0-9-]+", label)
command = [sys.executable, "-B", "-m", "unittest", "tools.test_source_receipts.ReceiptRangeNormalizationTests", "-q"]
verifier_paths = ["tools/test_source_receipts.py"] + sorted(
    p.relative_to(ROOT).as_posix()
    for p in (ROOT / "tests/scenarios/stale-state-reconciliation/.saipen").rglob("*") if p.is_file()
)
subject_paths = ["saipen/COMMAND_EFFECTS.json", "tools/saipen.py", "tools/saipen_engine/intake.py", "tools/saipen_engine/board.py",
                 "tools/saipen_engine/codec.py", "tools/saipen_engine/journal.py", "tools/saipen_engine/lock.py"]
def identities(paths):
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
verifier = {"command": command, "files": identities(verifier_paths), "python": sys.version}
subject = identities(subject_paths)
digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()
if label == "red":
    for rel in ("tools/saipen.py", "tools/saipen_engine/intake.py"):
        (DEST / (Path(rel).name + ".before")).write_bytes((ROOT / rel).read_bytes())
if label == "red-fixed":
    with tempfile.TemporaryDirectory(prefix="saipen-range-fixed-oracle-") as scratch:
        workspace = Path(scratch) / "subject"
        shutil.copytree(ROOT, workspace, ignore=lambda path, names: [
            name for name in names if name in {".git", "__pycache__", ".ruff_cache", ".pytest_cache"}
            or (Path(path) == ROOT and name == ".saipen")
        ])
        for rel in ("saipen/COMMAND_EFFECTS.json", "tools/saipen.py", "tools/saipen_engine/intake.py"):
            (workspace / rel).write_bytes((DEST / (Path(rel).name + ".before")).read_bytes())
        subject = {p: hashlib.sha256((workspace / p).read_bytes()).hexdigest() for p in subject_paths}
        assert {p: hashlib.sha256((workspace / p).read_bytes()).hexdigest() for p in verifier_paths} == verifier["files"]
        result = subprocess.run(command, cwd=workspace,
                                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                capture_output=True, text=True, encoding="utf-8", timeout=240)
else:
    result = subprocess.run(command, cwd=ROOT, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                            capture_output=True, text=True, encoding="utf-8", timeout=240)
output = result.stdout + result.stderr
(DEST / f"{label}.txt").write_text(output, encoding="utf-8")
record = {"exit_code": result.returncode, "verifier": digest(verifier)[:16], "subject": digest(subject)[:16],
          "verifier_identity": verifier, "subject_identity": subject,
          "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest()}
(DEST / f"{label}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(output[-700:])
print(json.dumps({k: record[k] for k in ("exit_code", "verifier", "subject")}))
sys.exit(result.returncode)
