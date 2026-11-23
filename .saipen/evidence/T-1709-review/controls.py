"""Freeze the reviewed subject and run the same oracle before and after correction."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.test_runner import _ignore_copy

HERE = Path(__file__).resolve().parent
SUBJECTS = (
    "tools/saipen_engine/audit_inbox.py",
    "tools/saipen_engine/audit_route.py",
    "tools/saipen_engine/router.py",
    "tools/saipen.py",
)
VERIFIER = "tools/test_t1709_audit_starvation.py"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(stage):
    target = HERE / ("subject-" + stage)
    if not target.exists():
        def ignore(directory, names):
            ignored = set(_ignore_copy(directory, names))
            if Path(directory) == ROOT:
                ignored.add(".saipen")
            return ignored
        shutil.copytree(ROOT, target, symlinks=True, ignore=ignore)
    verifier_files = {
        rel: digest((target / rel).read_bytes())
        for rel in (VERIFIER, "tools/test_audit_inbox.py", "tools/test_fixture_support.py")
    }
    verifier = digest(json.dumps(verifier_files, sort_keys=True).encode("utf-8"))
    files = {rel: digest((target / rel).read_bytes()) for rel in SUBJECTS}
    subject = digest(json.dumps(files, sort_keys=True).encode("utf-8"))
    proc = subprocess.run(
        [sys.executable, "-B", VERIFIER], cwd=target,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    output = proc.stdout + proc.stderr
    (HERE / (stage + ".txt")).write_text(output, encoding="utf-8")
    result = {
        "stage": stage, "snapshot": str(target), "exit_code": proc.returncode,
        "verifier": verifier, "subject": subject, "subject_files": files,
        "verifier_files": verifier_files, "python": sys.version,
        "command": ["python", "-B", VERIFIER], "output": stage + ".txt",
    }
    (HERE / (stage + ".json")).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(output[-7000:])
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1]))
