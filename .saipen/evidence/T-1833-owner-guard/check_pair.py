"""Run the identical owner-guard oracle against saved and current runtime bytes."""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
oracle = ROOT / "tools/test_t1833_verification_owner.py"
rows = []
for name in ("prefix", "postfix"):
    with tempfile.TemporaryDirectory(prefix="t1833-pair-") as raw:
        scratch = Path(raw)
        shutil.copytree(ROOT / "tools/saipen_engine", scratch / "saipen_engine",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy2(oracle, scratch / oracle.name)
        subject = scratch / "saipen_engine/process_tree.py"
        if name == "prefix":
            shutil.copy2(HERE / "prefix/process_tree.py", subject)
            shutil.copy2(HERE / "prefix/test_runner.py", scratch / "saipen_engine/test_runner.py")
        command = [sys.executable, "-B", "-m", "unittest", "discover",
                   "-s", ".", "-p", oracle.name, "-v"]
        result = subprocess.run(command, cwd=scratch, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=45)
        log = HERE / f"{name}-final-oracle-linux.log"
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        rows.append({"name": name, "oracle_sha256": hashlib.sha256(oracle.read_bytes()).hexdigest(),
                     "subject_sha256": hashlib.sha256(subject.read_bytes()).hexdigest(),
                     "subjects": {filename: hashlib.sha256(
                         (scratch / "saipen_engine" / filename).read_bytes()).hexdigest()
                         for filename in ("process_tree.py", "test_runner.py",
                                          "verification_bootstrap.py")},
                     "command": command, "exit_code": result.returncode, "log": log.name})
(HERE / "regression-pair.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
assert rows[0]["exit_code"] == 1 and rows[1]["exit_code"] == 0, rows
assert rows[0]["oracle_sha256"] == rows[1]["oracle_sha256"]
print(json.dumps(rows, indent=2))
