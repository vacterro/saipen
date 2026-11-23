"""The same real three-consumer oracle against indexed and current executors."""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
oracle = ROOT / "tools/test_t1832_single_flight.py"
rows = []
for label in ("prefix", "postfix"):
    with tempfile.TemporaryDirectory(prefix="t1832-concurrent-pair-") as raw:
        subject_root = Path(raw)
        for folder in ("tools", "saipen", "bootstrap", "extensions", "tests"):
            shutil.copytree(ROOT / folder, subject_root / folder,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".ruff_cache"))
        for path in ROOT.iterdir():
            if path.is_file():
                shutil.copy2(path, subject_root / path.name)
        subject = subject_root / "tools/saipen_engine/core_unit.py"
        if label == "prefix":
            shutil.copy2(HERE / "prefix-core_unit.py", subject)
        command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tools",
                   "-p", oracle.name, "-k", "test_three_compatible_consumers", "-v"]
        result = subprocess.run(command, cwd=subject_root, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=60)
        (HERE / f"{label}-concurrent.log").write_text(result.stdout + result.stderr,
                                                     encoding="utf-8")
        rows.append({"name": label, "command": command, "exit_code": result.returncode,
                     "oracle_sha256": hashlib.sha256(oracle.read_bytes()).hexdigest(),
                     "subject_sha256": hashlib.sha256(subject.read_bytes()).hexdigest()})
(HERE / "concurrent-pair.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
assert [row["exit_code"] for row in rows] == [1, 0], rows
print(json.dumps(rows, indent=2))
